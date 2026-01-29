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
import logging
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
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

# Time window for sending (to prevent duplicates from DST cron jobs)
# Only send if Israel time is between 5:45 AM and 6:30 AM
SEND_HOUR = 6
SEND_WINDOW_MINUTES_BEFORE = 15  # 5:45 AM
SEND_WINDOW_MINUTES_AFTER = 30  # 6:30 AM

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


def is_within_send_window() -> bool:
    """
    Check if current Israel time is within the send window.

    This prevents duplicate sends when both DST cron jobs run.
    Only the cron job that runs when it's ~6AM Israel time will actually send.

    Returns:
        True if within send window, False otherwise
    """
    israel_now = datetime.now(ISRAEL_TZ)
    current_hour = israel_now.hour
    current_minute = israel_now.minute

    # Convert to minutes since midnight for easier comparison
    current_minutes = current_hour * 60 + current_minute
    window_start = SEND_HOUR * 60 - SEND_WINDOW_MINUTES_BEFORE  # 5:45 AM = 345
    window_end = SEND_HOUR * 60 + SEND_WINDOW_MINUTES_AFTER  # 6:30 AM = 390

    is_within = window_start <= current_minutes <= window_end

    logger.info(
        f"Israel time: {israel_now.strftime('%H:%M')} - "
        f"Send window: {window_start // 60}:{window_start % 60:02d} - "
        f"{window_end // 60}:{window_end % 60:02d} - "
        f"Within window: {is_within}"
    )

    return is_within


def get_config() -> tuple[str, str]:
    """
    Get configuration from environment variables.

    Returns:
        Tuple of (bot_token, chat_id)

    Raises:
        ValueError: If required environment variables are not set
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")
    if not chat_id:
        raise ValueError("TELEGRAM_CHAT_ID environment variable is not set")

    return bot_token, chat_id


def convert_masechta_name(hebcal_name: str) -> str:
    """
    Convert Hebcal masechta name to AllDaf format.

    Args:
        hebcal_name: Masechta name from Hebcal API

    Returns:
        Masechta name in AllDaf format
    """
    return MASECHTA_NAME_MAP.get(hebcal_name, hebcal_name)


async def get_todays_daf() -> DafInfo:
    """
    Fetch today's Daf Yomi from Hebcal API.

    Uses Israel timezone to determine the correct date.

    Returns:
        DafInfo with masechta and daf number

    Raises:
        DafNotFoundError: If the daf cannot be determined
    """
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


async def get_jewish_history_video(daf: DafInfo) -> VideoInfo:
    """
    Find the Jewish History video for a specific daf.

    Args:
        daf: DafInfo with masechta and daf number

    Returns:
        VideoInfo with video details

    Raises:
        VideoNotFoundError: If the video cannot be found
    """
    masechta_lower = daf.masechta.lower()

    async with httpx.AsyncClient(
        follow_redirects=True, timeout=REQUEST_TIMEOUT
    ) as client:
        # Search the Jewish History series page
        try:
            response = await client.get(ALLDAF_SERIES_URL)
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise VideoNotFoundError(f"Failed to fetch AllDaf series page: {e}") from e

        soup = BeautifulSoup(response.text, "html.parser")

        # Look for video matching this masechta and daf
        page_url = None
        title = None

        for link in soup.find_all("a", href=True):
            href = link["href"]
            if not href.startswith("/p/"):
                continue

            link_text = link.get_text().strip()
            link_text_lower = link_text.lower()

            if masechta_lower not in link_text_lower:
                continue

            # Check for daf number match
            patterns = [
                f"{masechta_lower} {daf.daf}",
                f"{masechta_lower} daf {daf.daf}",
            ]

            if any(p in link_text_lower for p in patterns) or re.search(
                rf"{masechta_lower}\s+{daf.daf}\b", link_text_lower
            ):
                page_url = f"{ALLDAF_BASE_URL}{href}"
                title = link_text
                break

        if not page_url:
            raise VideoNotFoundError(
                f"Could not find Jewish History video for {daf.masechta} {daf.daf}"
            )

        # Fetch video page to get direct MP4 URL
        logger.info(f"Found video page: {page_url}")

        try:
            response = await client.get(page_url)
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise VideoNotFoundError(f"Failed to fetch video page: {e}") from e

        # Extract JWPlayer video URL
        video_url = None
        mp4_pattern = r"https://(?:cdn\.jwplayer\.com|content\.jwplatform\.com)/videos/([a-zA-Z0-9]+)\.mp4"
        mp4_match = re.search(mp4_pattern, response.text)

        if mp4_match:
            video_url = f"https://cdn.jwplayer.com/videos/{mp4_match.group(1)}.mp4"
            logger.info(f"Found video URL: {video_url}")
        else:
            logger.warning("Could not extract direct video URL, will send link only")

        return VideoInfo(
            title=title,
            page_url=page_url,
            video_url=video_url,
            masechta=daf.masechta,
            daf=daf.daf,
        )


async def send_to_telegram(video: VideoInfo, bot_token: str, chat_id: str) -> None:
    """
    Send the video to Telegram.

    Args:
        video: VideoInfo with video details
        bot_token: Telegram bot token
        chat_id: Telegram chat ID

    Raises:
        TelegramError: If sending fails
    """
    caption = (
        f"📚 *Today's Daf Yomi History*\n\n"
        f"*{video.masechta} {video.daf}*\n"
        f"{video.title}\n\n"
        f"[View on AllDaf.org]({video.page_url})"
    )

    bot = Bot(token=bot_token)

    try:
        if video.video_url:
            logger.info("Sending embedded video...")
            await bot.send_video(
                chat_id=chat_id,
                video=video.video_url,
                caption=caption,
                parse_mode="Markdown",
                supports_streaming=True,
            )
        else:
            logger.info("Sending link (no direct video URL available)...")
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode="Markdown",
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


async def main() -> int:
    """
    Main entry point.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        # Check if we're within the send window (prevents duplicates from DST cron jobs)
        # Skip SKIP_TIME_CHECK for manual testing or webhook triggers
        skip_time_check = os.environ.get("SKIP_TIME_CHECK", "").lower() == "true"
        if not skip_time_check and not is_within_send_window():
            logger.info("Outside send window - skipping to prevent duplicate sends")
            return 0

        # Get configuration
        bot_token, chat_id = get_config()

        # Get today's daf
        daf = await get_todays_daf()

        # Find the video
        video = await get_jewish_history_video(daf)
        logger.info(f"Found video: {video.title}")

        # Send to Telegram
        await send_to_telegram(video, bot_token, chat_id)

        # Send to unified Torah Yomi channel
        await send_to_unified_channel(video)

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
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
