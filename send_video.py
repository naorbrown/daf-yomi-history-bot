#!/usr/bin/env python3
"""
Daf Yomi History Bot - Daily Video Sender

Fetches the daily Daf Yomi Jewish History video from AllDaf.org
and sends it to a Telegram chat.

This script is designed to run via GitHub Actions on a daily schedule.
It includes a time window check to prevent duplicate sends from DST cron jobs.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup
from telegram import Bot
from telegram.error import TelegramError

from unified import is_unified_channel_enabled, publish_video_to_unified_channel, publish_text_to_unified_channel

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Constants
ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")
ALLDAF_BASE_URL = "https://alldaf.org"
ALLDAF_SERIES_URL = f"{ALLDAF_BASE_URL}/series/3940"
HEBCAL_API_URL = "https://www.hebcal.com/hebcal"
REQUEST_TIMEOUT = 30.0

# State file for tracking last broadcast date
# Deduplication is handled via this state file, not time windows.
# This is more robust than time-based checks because GitHub Actions
# cron jobs can be delayed by 20-90+ minutes unpredictably.
LAST_BROADCAST_FILE = ".github/state/last_broadcast.json"

# Masechta name mapping: Hebcal uses different transliterations than AllDaf
MASECHTA_NAME_MAP: dict[str, str] = {
    "Berakhot": "Berachos",
    "Shabbat": "Shabbos",
    "Sukkah": "Succah",
    "Taanit": "Taanis",
    "Megillah": "Megilah",
    "Chagigah": "Chagiga",
    "Yevamot": "Yevamos",
    "Ketubot": "Kesuvos",
    "Gittin": "Gitin",
    "Kiddushin": "Kidushin",
    "Bava Kamma": "Bava Kama",
    "Bava Batra": "Bava Basra",
    "Makkot": "Makos",
    "Shevuot": "Shevuos",
    "Horayot": "Horayos",
    "Menachot": "Menachos",
    "Chullin": "Chulin",
    "Bekhorot": "Bechoros",
    "Arakhin": "Erchin",
    "Keritot": "Kerisus",
    "Niddah": "Nidah",
}


@dataclass
class DafInfo:
    """Information about the current Daf Yomi."""

    masechta: str
    daf: int


@dataclass
class VideoInfo:
    """Information about a Jewish History video."""

    title: str
    page_url: str
    video_url: Optional[str]
    masechta: str
    daf: int


class DafYomiError(Exception):
    """Base exception for Daf Yomi bot errors."""

    pass


class DafNotFoundError(DafYomiError):
    """Raised when the daily daf cannot be determined."""

    pass


class VideoNotFoundError(DafYomiError):
    """Raised when the video cannot be found."""

    pass



def get_config() -> tuple[str, Optional[str]]:
    """
    Get configuration from environment variables.

    Returns:
        Tuple of (bot_token, chat_id) - chat_id may be None if using subscribers only

    Raises:
        ValueError: If bot token is not set
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

    return bot_token, chat_id


def get_subscribers() -> list[int]:
    """
    Get list of subscriber chat IDs from state file.

    Returns:
        List of chat IDs
    """
    # Path relative to repo root
    workspace = os.environ.get("GITHUB_WORKSPACE", ".")
    subscribers_file = Path(workspace) / ".github" / "state" / "subscribers.json"

    if subscribers_file.exists():
        try:
            data = json.loads(subscribers_file.read_text())
            return data.get("chat_ids", [])
        except (json.JSONDecodeError, KeyError):
            logger.warning("Failed to read subscribers file")
            return []
    return []


def convert_masechta_name(hebcal_name: str) -> str:
    """
    Convert Hebcal masechta name to AllDaf format.

    Args:
        hebcal_name: Masechta name from Hebcal API

    Returns:
        Masechta name in AllDaf format
    """
    return MASECHTA_NAME_MAP.get(hebcal_name, hebcal_name)


def get_last_broadcast_date() -> Optional[str]:
    """
    Get the last broadcast date from state file.

    Returns:
        Date string (YYYY-MM-DD) or None if not found
    """
    workspace = os.environ.get("GITHUB_WORKSPACE", ".")
    broadcast_file = Path(workspace) / LAST_BROADCAST_FILE

    if broadcast_file.exists():
        try:
            data = json.loads(broadcast_file.read_text())
            return data.get("date")
        except (json.JSONDecodeError, KeyError):
            logger.warning("Failed to read last broadcast file")
            return None
    return None


def save_last_broadcast_date(date_str: str) -> None:
    """
    Save the last broadcast date to state file.

    Args:
        date_str: Date string (YYYY-MM-DD) to save
    """
    workspace = os.environ.get("GITHUB_WORKSPACE", ".")
    broadcast_file = Path(workspace) / LAST_BROADCAST_FILE

    # Ensure directory exists
    broadcast_file.parent.mkdir(parents=True, exist_ok=True)

    broadcast_file.write_text(json.dumps({"date": date_str}, indent=2))
    logger.info(f"Saved last broadcast date: {date_str}")


def has_already_broadcast_today() -> bool:
    """
    Check if we've already broadcast today.

    Returns:
        True if already broadcast today, False otherwise
    """
    israel_now = datetime.now(ISRAEL_TZ)
    today_str = israel_now.strftime("%Y-%m-%d")

    last_broadcast = get_last_broadcast_date()
    if last_broadcast == today_str:
        logger.info(f"Already broadcast today ({today_str})")
        return True
    return False


async def get_todays_daf() -> DafInfo:
    """
    Fetch today's Daf Yomi from Hebcal API.

    Uses Israel timezone to determine the correct date.

    Returns:
        DafInfo with masechta and daf number

    Raises:
        DafNotFoundError: If the daf cannot be determined
    """
    override_date = os.environ.get("OVERRIDE_DATE", "").strip()
    if override_date:
        today_str = override_date
        logger.info(f"Using override date: {today_str}")
    else:
        israel_now = datetime.now(ISRAEL_TZ)
        today_str = israel_now.strftime("%Y-%m-%d")

    params = {
        "v": "1",
        "cfg": "json",
        "F": "on",  # Daf Yomi
        "start": today_str,
        "end": today_str,
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        try:
            response = await client.get(HEBCAL_API_URL, params=params)
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise DafNotFoundError(f"Failed to fetch from Hebcal API: {e}") from e

        data = response.json()

        for item in data.get("items", []):
            if item.get("category") == "dafyomi":
                title = item.get("title", "")
                match = re.match(r"(.+)\s+(\d+)", title)
                if match:
                    hebcal_masechta = match.group(1)
                    daf = int(match.group(2))
                    alldaf_masechta = convert_masechta_name(hebcal_masechta)

                    logger.info(f"Today's daf ({today_str}): {alldaf_masechta} {daf}")
                    return DafInfo(masechta=alldaf_masechta, daf=daf)

        raise DafNotFoundError(f"No Daf Yomi found in Hebcal for {today_str}")


def _get_masechta_search_names(masechta: str) -> set[str]:
    """
    Get all name variants to search for a masechta.

    Different sources use different transliterations (e.g., Menachot vs Menachos).
    Returns lowercase variants to match against.
    """
    names = {masechta.lower()}
    # Add Hebcal variant (reverse lookup)
    for hebcal_name, alldaf_name in MASECHTA_NAME_MAP.items():
        if alldaf_name == masechta:
            names.add(hebcal_name.lower())
            break
    # Also check if masechta IS a Hebcal name that maps to something
    if masechta in MASECHTA_NAME_MAP:
        names.add(MASECHTA_NAME_MAP[masechta].lower())
    return names


def _match_daf_in_text(link_text_lower: str, search_names: set[str], daf_num: int) -> bool:
    """Check if link text matches any masechta name variant + daf number."""
    for name in search_names:
        if name not in link_text_lower:
            continue
        patterns = [
            f"{name} {daf_num}",
            f"{name} daf {daf_num}",
        ]
        if any(p in link_text_lower for p in patterns) or re.search(
            rf"{name}\s+{daf_num}\b", link_text_lower
        ):
            return True
    return False


def _get_cached_page_id() -> Optional[int]:
    """Get the page ID from the last cached video URL."""
    workspace = os.environ.get("GITHUB_WORKSPACE", ".")
    cache_file = Path(workspace) / ".github" / "state" / "video_cache.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text())
            page_url = data.get("page_url", "")
            match = re.search(r"/p/(\d+)", page_url)
            if match:
                return int(match.group(1))
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
    return None


async def get_jewish_history_video(daf: DafInfo) -> VideoInfo:
    """
    Find the Jewish History video for a specific daf.

    Uses a multi-strategy approach:
    1. Scrape the AllDaf series page with multiple name variants
    2. Fall back to trying sequential page IDs near the last known video

    Args:
        daf: DafInfo with masechta and daf number

    Returns:
        VideoInfo with video details

    Raises:
        VideoNotFoundError: If the video cannot be found
    """
    search_names = _get_masechta_search_names(daf.masechta)
    logger.info(f"Searching for {daf.masechta} {daf.daf} (variants: {search_names})")

    async with httpx.AsyncClient(
        follow_redirects=True, timeout=REQUEST_TIMEOUT
    ) as client:
        # Strategy 1: Search the Jewish History series page
        page_url, title = await _search_series_page(client, search_names, daf)

        # Strategy 2: Try sequential page IDs near the last known video
        if not page_url:
            logger.info("Video not found on series page, trying adjacent page IDs...")
            page_url, title = await _search_adjacent_pages(client, search_names, daf)

        if not page_url:
            raise VideoNotFoundError(
                f"Could not find Jewish History video for {daf.masechta} {daf.daf}"
            )

        # Fetch video page to get direct MP4 URL
        logger.info(f"Found video page: {page_url}")
        video_url = await _extract_video_url(client, page_url)

        return VideoInfo(
            title=title or f"{daf.masechta} {daf.daf}",
            page_url=page_url,
            video_url=video_url,
            masechta=daf.masechta,
            daf=daf.daf,
        )


async def _search_series_page(
    client: httpx.AsyncClient, search_names: set[str], daf: DafInfo
) -> tuple[Optional[str], Optional[str]]:
    """Search the AllDaf series page for the video. Returns (page_url, title)."""
    try:
        response = await client.get(ALLDAF_SERIES_URL)
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning(f"Failed to fetch AllDaf series page: {e}")
        return None, None

    soup = BeautifulSoup(response.text, "html.parser")

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if not href.startswith("/p/"):
            continue

        link_text = link.get_text().strip()
        link_text_lower = link_text.lower()

        if _match_daf_in_text(link_text_lower, search_names, daf.daf):
            return f"{ALLDAF_BASE_URL}{href}", link_text

    return None, None


async def _search_adjacent_pages(
    client: httpx.AsyncClient, search_names: set[str], daf: DafInfo
) -> tuple[Optional[str], Optional[str]]:
    """Try sequential AllDaf page IDs near the last cached video. Returns (page_url, title)."""
    last_page_id = _get_cached_page_id()
    if last_page_id is None:
        logger.info("No cached page ID available for adjacent search")
        return None, None

    logger.info(f"Trying page IDs near {last_page_id}...")

    # Try IDs both forward and backward from the last known video
    # Forward is more likely (next daf = next ID), but try both directions
    offsets = list(range(1, 16)) + list(range(-1, -6, -1))

    for offset in offsets:
        candidate_id = last_page_id + offset
        candidate_url = f"{ALLDAF_BASE_URL}/p/{candidate_id}"

        try:
            response = await client.get(candidate_url)
            if response.status_code != 200:
                continue

            page_text_lower = response.text.lower()

            # Quick check: does this page contain the masechta name and daf number?
            has_name = any(name in page_text_lower for name in search_names)
            has_daf = str(daf.daf) in page_text_lower
            if not has_name or not has_daf:
                continue

            # Verify with stricter matching
            for name in search_names:
                if re.search(rf"{name}\s+{daf.daf}\b", page_text_lower):
                    # Extract title from the page
                    soup = BeautifulSoup(response.text, "html.parser")
                    title_tag = soup.find("h1") or soup.find("title")
                    title = title_tag.get_text().strip() if title_tag else f"{daf.masechta} {daf.daf}"
                    logger.info(f"Found video via adjacent page ID: {candidate_url} ({title})")
                    return candidate_url, title

        except httpx.HTTPError:
            continue

    return None, None


async def _extract_video_url(client: httpx.AsyncClient, page_url: str) -> Optional[str]:
    """Fetch a video page and extract the direct MP4 URL."""
    try:
        response = await client.get(page_url)
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning(f"Failed to fetch video page: {e}")
        return None

    mp4_pattern = r"https://(?:cdn\.jwplayer\.com|content\.jwplatform\.com)/videos/([a-zA-Z0-9]+)\.mp4"
    mp4_match = re.search(mp4_pattern, response.text)

    if mp4_match:
        video_url = f"https://cdn.jwplayer.com/videos/{mp4_match.group(1)}.mp4"
        logger.info(f"Found video URL: {video_url}")
        return video_url

    logger.warning("Could not extract direct video URL, will send link only")
    return None


async def send_to_telegram(video: VideoInfo, bot: Bot, chat_id: str) -> None:
    """
    Send the video to Telegram.

    Args:
        video: VideoInfo with video details
        bot: Initialized Telegram Bot instance
        chat_id: Telegram chat ID

    Raises:
        TelegramError: If sending fails
    """
    caption = (
        f"Daily Daf Yomi History\n\n"
        f"{video.masechta} {video.daf}\n"
        f"{video.title}\n\n"
        f"{video.page_url}"
    )

    try:
        if video.video_url:
            logger.info("Sending embedded video...")
            await bot.send_video(
                chat_id=chat_id,
                video=video.video_url,
                caption=caption,
                supports_streaming=True,
            )
        else:
            logger.info("Sending link (no direct video URL available)...")
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                disable_web_page_preview=False,
            )

        logger.info("Message sent successfully!")

    except TelegramError as e:
        logger.error(f"Failed to send Telegram message: {e}")
        raise


async def send_to_unified_channel(video: VideoInfo) -> None:
    """
    Send a condensed message to the unified Torah Yomi channel.

    Args:
        video: VideoInfo with video details
    """
    if not is_unified_channel_enabled():
        logger.debug("Unified channel not configured, skipping")
        return

    try:
        caption = (
            f"<b>{video.masechta} {video.daf}</b>\n"
            f"{video.title}\n\n"
            f'<a href="{video.page_url}">View on AllDaf.org</a>'
        )

        if video.video_url:
            await publish_video_to_unified_channel(video.video_url, caption)
        else:
            await publish_text_to_unified_channel(caption)

        logger.info("Published to unified channel successfully")

    except Exception as e:
        # Don't fail the main broadcast if unified channel fails
        logger.error(f"Failed to publish to unified channel: {e}")


async def broadcast_to_subscribers(
    video: VideoInfo, bot: Bot, exclude_chat_id: Optional[str] = None
) -> tuple[int, int]:
    """
    Broadcast video to all subscribers.

    Args:
        video: VideoInfo with video details
        bot: Initialized Telegram Bot instance
        exclude_chat_id: Optional chat ID to exclude (to prevent duplicates)

    Returns:
        Tuple of (success_count, failure_count)
    """
    subscribers = get_subscribers()
    if not subscribers:
        logger.info("No subscribers to broadcast to")
        return 0, 0

    # Filter out the excluded chat ID to prevent duplicate messages
    if exclude_chat_id:
        excluded_id = int(exclude_chat_id) if exclude_chat_id.lstrip("-").isdigit() else None
        if excluded_id and excluded_id in subscribers:
            subscribers = [s for s in subscribers if s != excluded_id]
            logger.info(f"Excluded main chat ID {excluded_id} from subscriber broadcast")

    if not subscribers:
        logger.info("No additional subscribers to broadcast to (all excluded)")
        return 0, 0

    logger.info(f"Broadcasting to {len(subscribers)} subscribers...")
    success = 0
    failed = 0

    for chat_id in subscribers:
        try:
            await send_to_telegram(video, bot, str(chat_id))
            success += 1
        except Exception as e:
            logger.error(f"Failed to send to {chat_id}: {e}")
            failed += 1

    logger.info(f"Broadcast complete: {success} succeeded, {failed} failed")
    return success, failed


async def main() -> int:
    """
    Main entry point.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        skip_dedup_check = os.environ.get("SKIP_TIME_CHECK", "").lower() == "true"

        # Log current Israel time for debugging
        israel_now = datetime.now(ISRAEL_TZ)
        logger.info(f"Israel time: {israel_now.strftime('%Y-%m-%d %H:%M')}")

        # Check if we've already broadcast today (prevents duplicate sends)
        if not skip_dedup_check and has_already_broadcast_today():
            logger.info("Already broadcast today - skipping to prevent duplicates")
            return 0

        # Get configuration
        bot_token, chat_id = get_config()

        # Get today's daf
        daf = await get_todays_daf()

        # Find the video
        video = await get_jewish_history_video(daf)
        logger.info(f"Found video: {video.title}")

        # Track if any broadcast succeeded
        broadcast_succeeded = False

        # Create Bot once with proper async lifecycle (required by python-telegram-bot v20+)
        async with Bot(token=bot_token) as bot:
            # Send to main chat ID (if configured) for backwards compatibility
            if chat_id:
                try:
                    await send_to_telegram(video, bot, chat_id)
                    broadcast_succeeded = True
                except Exception as e:
                    logger.error(f"Failed to send to main chat: {e}")

            # Broadcast to all subscribers (excluding main chat to prevent duplicates)
            success_count, _ = await broadcast_to_subscribers(video, bot, exclude_chat_id=chat_id)
            if success_count > 0:
                broadcast_succeeded = True

        # Send to unified Torah Yomi channel
        await send_to_unified_channel(video)

        # Save broadcast date if any message was sent successfully
        if broadcast_succeeded:
            israel_now = datetime.now(ISRAEL_TZ)
            today_str = israel_now.strftime("%Y-%m-%d")
            save_last_broadcast_date(today_str)

        return 0

    except VideoNotFoundError as e:
        # Not every daf has a Jewish History video — this is expected.
        # Don't save broadcast state so the fallback can retry if the
        # video is uploaded later today.
        logger.warning(f"No video available: {e}")
        return 0

    except DafYomiError as e:
        logger.error(f"Daf Yomi error: {e}")
        return 1

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return 1

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    # Fallback mode: only run if it's past broadcast time in Israel
    # Used by poll-commands workflow as a safety net for cron failures
    is_fallback = "--fallback" in sys.argv
    if is_fallback:
        israel_now = datetime.now(ISRAEL_TZ)
        if israel_now.hour < 3 or (israel_now.hour == 3 and israel_now.minute < 30):
            logger.info("Fallback: too early (before 3:30 AM IST), skipping")
            sys.exit(0)
        logger.info("Fallback mode: running broadcast (past 3:30 AM IST)")

    exit_code = asyncio.run(main())

    # In fallback mode, treat video-not-found as non-fatal since the
    # daily_video workflow will handle retries. This prevents blocking
    # the poll-commands workflow from responding to user commands.
    if is_fallback and exit_code != 0:
        logger.info("Fallback: broadcast failed (video may not be available yet), continuing")
        sys.exit(0)

    sys.exit(exit_code)
