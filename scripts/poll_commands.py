#!/usr/bin/env python3
"""
Daf Yomi History Bot - Command Polling for GitHub Actions

Polls Telegram for new messages and responds to commands.
Designed to run periodically via GitHub Actions (every 5 minutes).

State is stored in .github/state/last_update_id.json to track processed messages.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import time
from typing import Any, Optional
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# Paths - use GITHUB_WORKSPACE if available, otherwise script-relative
def get_repo_root() -> Path:
    """Get the repository root directory."""
    # In GitHub Actions, GITHUB_WORKSPACE is the repo root
    workspace = os.environ.get("GITHUB_WORKSPACE")
    if workspace:
        return Path(workspace)
    # Fallback: assume script is in {repo}/scripts/
    return Path(__file__).parent.parent


REPO_ROOT = get_repo_root()
STATE_DIR = REPO_ROOT / ".github" / "state"
STATE_FILE = STATE_DIR / "last_update_id.json"
RATE_LIMIT_FILE = STATE_DIR / "rate_limits.json"
VIDEO_CACHE_FILE = STATE_DIR / "video_cache.json"
SUBSCRIBERS_FILE = STATE_DIR / "subscribers.json"

# Constants
ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")
ALLDAF_BASE_URL = "https://alldaf.org"
ALLDAF_SERIES_URL = f"{ALLDAF_BASE_URL}/series/3940"
HEBCAL_API_URL = "https://www.hebcal.com/hebcal"
REQUEST_TIMEOUT = 30.0
TELEGRAM_API_BASE = "https://api.telegram.org/bot"

# Rate limiting: 5 requests per 60 seconds per user
RATE_LIMIT_MAX_REQUESTS = 5
RATE_LIMIT_WINDOW_SECONDS = 60

# Masechta name mapping: Hebcal -> AllDaf format
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

# Bot messages (plain text - no Markdown to avoid parsing issues)
WELCOME_MESSAGE = """Welcome to Daf Yomi History Bot!

You're now subscribed to daily Jewish History videos by Dr. Henry Abramson, matching the Daf Yomi schedule.

Daily broadcast: 3:00 AM Israel time
On-demand: Use /today anytime"""

ERROR_MESSAGE = """Sorry, I couldn't find today's video. Please try again later.

Visit AllDaf.org directly: https://alldaf.org/series/3940"""

RATE_LIMITED_MESSAGE = "Too many requests. Please wait a minute and try again."


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


class TelegramAPI:
    """Simple Telegram Bot API client with connection reuse for performance."""

    def __init__(self, token: str):
        self.token = token
        self.base_url = f"{TELEGRAM_API_BASE}{token}"
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create a reusable HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=REQUEST_TIMEOUT,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def delete_webhook(self) -> bool:
        """Delete any existing webhook to enable polling."""
        logger.info("Deleting webhook to ensure polling works...")
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.base_url}/deleteWebhook",
                json={"drop_pending_updates": False},
            )
            response.raise_for_status()
            data = response.json()

            if data.get("ok"):
                logger.info("Webhook deleted successfully (or no webhook was set)")
                return True
            else:
                logger.warning(f"deleteWebhook response: {data}")
                return False
        except Exception as e:
            logger.error(f"Error deleting webhook: {type(e).__name__}: {e}")
            return False

    async def get_updates(self, offset: Optional[int] = None) -> list[dict[str, Any]]:
        """Fetch new updates from Telegram."""
        params: dict[str, Any] = {"timeout": 0, "limit": 100}
        if offset is not None:
            params["offset"] = offset

        logger.info(f"Calling getUpdates with offset={offset}")
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.base_url}/getUpdates",
                json=params,
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("ok"):
                logger.error(f"getUpdates failed: {data}")
                raise RuntimeError(f"Telegram API error: {data}")

            updates = data.get("result", [])
            logger.info(f"Received {len(updates)} updates from Telegram")
            return updates
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                logger.error(
                    "getUpdates returned 409 Conflict - a webhook is blocking polling! "
                    "Run 'python scripts/fix_bot.py' to diagnose and fix."
                )
            else:
                logger.error(f"HTTP error calling getUpdates: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error calling getUpdates: {type(e).__name__}: {e}")
            raise

    async def send_message(self, chat_id: int, text: str) -> dict[str, Any]:
        """Send a text message."""
        logger.info(f"Sending message to chat_id={chat_id}")
        client = await self._get_client()
        response = await client.post(
            f"{self.base_url}/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            logger.error(f"sendMessage failed: {data}")
            raise RuntimeError(f"Telegram API error: {data}")
        logger.info(f"Message sent successfully to chat_id={chat_id}")
        return data

    async def send_video(
        self, chat_id: int, video_url: str, caption: str
    ) -> dict[str, Any]:
        """Send a video message."""
        logger.info(f"Sending video to chat_id={chat_id}")
        # Use longer timeout for video uploads
        client = await self._get_client()
        response = await client.post(
            f"{self.base_url}/sendVideo",
            json={
                "chat_id": chat_id,
                "video": video_url,
                "caption": caption,
                "supports_streaming": True,
            },
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            logger.error(f"sendVideo failed: {data}")
            raise RuntimeError(f"Telegram API error: {data}")
        logger.info(f"Video sent successfully to chat_id={chat_id}")
        return data


class StateManager:
    """Manages persistent state for the bot."""

    def __init__(self):
        STATE_DIR.mkdir(parents=True, exist_ok=True)

    def get_last_update_id(self) -> Optional[int]:
        """Get the last processed update ID."""
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text())
                return data.get("last_update_id")
            except (json.JSONDecodeError, KeyError):
                return None
        return None

    def set_last_update_id(self, update_id: int) -> None:
        """Save the last processed update ID."""
        STATE_FILE.write_text(json.dumps({"last_update_id": update_id}, indent=2))

    def get_rate_limits(self) -> dict[str, list[float]]:
        """Get rate limit data."""
        if RATE_LIMIT_FILE.exists():
            try:
                return json.loads(RATE_LIMIT_FILE.read_text())
            except json.JSONDecodeError:
                return {}
        return {}

    def save_rate_limits(self, data: dict[str, list[float]]) -> None:
        """Save rate limit data."""
        RATE_LIMIT_FILE.write_text(json.dumps(data, indent=2))

    def get_cached_video(self, date_str: str) -> Optional[dict[str, Any]]:
        """Get cached video info if it exists and matches today's date."""
        if VIDEO_CACHE_FILE.exists():
            try:
                data = json.loads(VIDEO_CACHE_FILE.read_text())
                if data.get("date") == date_str:
                    logger.info(f"Cache hit for date {date_str}")
                    return data
                logger.info(f"Cache miss: cached date {data.get('date')} != {date_str}")
            except json.JSONDecodeError:
                logger.warning("Failed to parse video cache file")
        return None

    def save_video_cache(self, video_info: dict[str, Any]) -> None:
        """Save video info to cache."""
        VIDEO_CACHE_FILE.write_text(json.dumps(video_info, indent=2))
        logger.info(f"Cached video info for date {video_info.get('date')}")

    def get_subscribers(self) -> list[int]:
        """Get list of subscriber chat IDs."""
        if SUBSCRIBERS_FILE.exists():
            try:
                data = json.loads(SUBSCRIBERS_FILE.read_text())
                return data.get("chat_ids", [])
            except json.JSONDecodeError:
                return []
        return []

    def add_subscriber(self, chat_id: int) -> bool:
        """Add a subscriber. Returns True if newly added, False if already subscribed."""
        subscribers = self.get_subscribers()
        if chat_id in subscribers:
            return False
        subscribers.append(chat_id)
        SUBSCRIBERS_FILE.write_text(json.dumps({"chat_ids": subscribers}, indent=2))
        logger.info(f"Added subscriber: {chat_id} (total: {len(subscribers)})")
        return True


class RateLimiter:
    """Per-user rate limiting."""

    def __init__(self, state: StateManager):
        self.state = state
        self.requests: dict[str, list[float]] = defaultdict(list)
        self._load()

    def _load(self) -> None:
        """Load rate limit data from state."""
        data = self.state.get_rate_limits()
        for user_id, timestamps in data.items():
            self.requests[user_id] = timestamps

    def _save(self) -> None:
        """Save rate limit data to state."""
        self.state.save_rate_limits(dict(self.requests))

    def _cleanup_old_requests(self, user_id: str) -> None:
        """Remove expired timestamps."""
        now = time()
        cutoff = now - RATE_LIMIT_WINDOW_SECONDS
        self.requests[user_id] = [t for t in self.requests[user_id] if t > cutoff]

    def is_allowed(self, user_id: int) -> bool:
        """Check if a user's request is allowed."""
        user_key = str(user_id)
        self._cleanup_old_requests(user_key)

        if len(self.requests[user_key]) >= RATE_LIMIT_MAX_REQUESTS:
            return False

        self.requests[user_key].append(time())
        self._save()
        return True


def convert_masechta_name(hebcal_name: str) -> str:
    """Convert Hebcal masechta name to AllDaf format."""
    return MASECHTA_NAME_MAP.get(hebcal_name, hebcal_name)


async def get_todays_daf() -> DafInfo:
    """Fetch today's Daf Yomi from Hebcal API."""
    israel_now = datetime.now(ISRAEL_TZ)
    today_str = israel_now.strftime("%Y-%m-%d")

    params = {
        "v": "1",
        "cfg": "json",
        "F": "on",
        "start": today_str,
        "end": today_str,
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.get(HEBCAL_API_URL, params=params)
        response.raise_for_status()
        data = response.json()

        for item in data.get("items", []):
            if item.get("category") == "dafyomi":
                title = item.get("title", "")
                match = re.match(r"(.+)\s+(\d+)", title)
                if match:
                    hebcal_masechta = match.group(1)
                    daf = int(match.group(2))
                    alldaf_masechta = convert_masechta_name(hebcal_masechta)
                    logger.info(f"Today's daf: {alldaf_masechta} {daf}")
                    return DafInfo(masechta=alldaf_masechta, daf=daf)

        raise ValueError(f"No Daf Yomi found for {today_str}")


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
    if VIDEO_CACHE_FILE.exists():
        try:
            data = json.loads(VIDEO_CACHE_FILE.read_text())
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
    """
    search_names = _get_masechta_search_names(daf.masechta)
    logger.info(f"Searching for {daf.masechta} {daf.daf} (variants: {search_names})")

    async with httpx.AsyncClient(
        follow_redirects=True, timeout=REQUEST_TIMEOUT
    ) as client:
        # Strategy 1: Search the series page
        page_url, title = await _search_series_page(client, search_names, daf)

        # Strategy 2: Try sequential page IDs near the last known video
        if not page_url:
            logger.info("Video not found on series page, trying adjacent page IDs...")
            page_url, title = await _search_adjacent_pages(client, search_names, daf)

        if not page_url:
            raise ValueError(f"Video not found for {daf.masechta} {daf.daf}")

        # Fetch video page for MP4 URL
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
            logger.info(f"Found video on series page: {link_text}")
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

    mp4_pattern = (
        r"https://(?:cdn\.jwplayer\.com|content\.jwplatform\.com)"
        r"/videos/([a-zA-Z0-9]+)\.mp4"
    )
    mp4_match = re.search(mp4_pattern, response.text)

    if mp4_match:
        video_url = f"https://cdn.jwplayer.com/videos/{mp4_match.group(1)}.mp4"
        logger.info(f"Found video URL: {video_url}")
        return video_url

    logger.warning("Could not extract direct video URL, will send link only")
    return None


def parse_command(text: Optional[str]) -> Optional[str]:
    """Parse command from message text."""
    if not text:
        return None

    text = text.strip()
    if not text.startswith("/"):
        return None

    # Extract command (handle /command@botname format)
    match = re.match(r"/(\w+)(?:@\w+)?", text)
    if match:
        return match.group(1).lower()
    return None


async def send_todays_video(
    api: TelegramAPI,
    chat_id: int,
    state: StateManager,
    user_id: int,
) -> bool:
    """Send today's video to the user. Returns True on success."""
    try:
        # Get today's date in Israel timezone for cache key
        israel_now = datetime.now(ISRAEL_TZ)
        today_str = israel_now.strftime("%Y-%m-%d")

        # Check cache first for near-instant response
        cached = state.get_cached_video(today_str)
        if cached:
            video = VideoInfo(
                title=cached["title"],
                page_url=cached["page_url"],
                video_url=cached.get("video_url"),
                masechta=cached["masechta"],
                daf=cached["daf"],
            )
            logger.info(f"Using cached video: {video.title}")
        else:
            # Fetch from external APIs and cache result
            daf = await get_todays_daf()
            video = await get_jewish_history_video(daf)

            # Cache the result for future requests
            cache_data = {
                "date": today_str,
                "title": video.title,
                "page_url": video.page_url,
                "video_url": video.video_url,
                "masechta": video.masechta,
                "daf": video.daf,
            }
            state.save_video_cache(cache_data)

        caption = (
            f"{video.masechta} {video.daf}\n"
            f"{video.title}\n\n"
            f"{video.page_url}"
        )

        if video.video_url:
            try:
                await api.send_video(chat_id, video.video_url, caption)
            except Exception as video_err:
                logger.warning(f"send_video failed, falling back to text: {video_err}")
                await api.send_message(chat_id, caption)
        else:
            await api.send_message(chat_id, caption)

        logger.info(f"Sent video to user {user_id}: {video.title}")
        return True

    except Exception as e:
        logger.error(f"Error fetching video: {e}")
        try:
            await api.send_message(chat_id, ERROR_MESSAGE)
        except Exception as send_err:
            logger.error(f"Failed to send error message: {send_err}")
        return False


async def handle_command(
    api: TelegramAPI,
    chat_id: int,
    command: str,
    rate_limiter: RateLimiter,
    user_id: int,
    state: StateManager,
) -> None:
    """Handle a bot command."""
    # Rate limit check (except for start)
    if command != "start" and not rate_limiter.is_allowed(user_id):
        await api.send_message(chat_id, RATE_LIMITED_MESSAGE)
        logger.info(f"Rate limited user {user_id}")
        return

    if command == "start":
        # Register subscriber for daily broadcasts
        is_new = state.add_subscriber(chat_id)
        # Send welcome message, then today's video
        await api.send_message(chat_id, WELCOME_MESSAGE)
        await send_todays_video(api, chat_id, state, user_id)
        logger.info(f"Sent welcome + video to user {user_id} (new subscriber: {is_new})")

    elif command in ("today", "help"):
        # /today and /help both send today's video
        await send_todays_video(api, chat_id, state, user_id)

    else:
        # Unknown command - ignore silently
        logger.debug(f"Unknown command: {command}")


async def process_updates(api: TelegramAPI, state: StateManager) -> int:
    """Process pending Telegram updates. Returns count of processed updates."""
    # Load last update ID, default to 0 if not found (matches nachyomi-bot pattern)
    last_update_id = state.get_last_update_id()
    if last_update_id is None:
        last_update_id = 0
        logger.info("No state file found, starting from offset 1")

    # Always use offset = lastUpdateId + 1 (nachyomi-bot pattern)
    offset = last_update_id + 1
    logger.info(f"Fetching updates with offset={offset}")

    updates = await api.get_updates(offset)
    if not updates:
        logger.info("No new updates")
        # Still save state to ensure file exists
        state.set_last_update_id(last_update_id)
        return 0

    rate_limiter = RateLimiter(state)
    processed = 0
    max_update_id = last_update_id

    for update in updates:
        update_id = update.get("update_id")
        message = update.get("message", {})
        text = message.get("text")
        chat_id = message.get("chat", {}).get("id")
        user_id = message.get("from", {}).get("id")

        # Track highest update_id seen
        if update_id and update_id > max_update_id:
            max_update_id = update_id

        if not chat_id or not user_id:
            logger.warning(f"Skipping update {update_id}: missing chat_id or user_id")
            continue

        command = parse_command(text)
        if command:
            logger.info(f"Processing command /{command} from user {user_id}")
            try:
                await handle_command(api, chat_id, command, rate_limiter, user_id, state)
                processed += 1
            except Exception as e:
                logger.error(f"Failed to handle command /{command} for user {user_id}: {e}")
                # Continue processing other updates even if one fails

    # Save highest update_id AFTER processing all updates (nachyomi-bot pattern)
    if max_update_id > last_update_id:
        state.set_last_update_id(max_update_id)
        logger.info(f"Saved last_update_id={max_update_id}")

    logger.info(f"Processed {processed} command(s) from {len(updates)} update(s)")
    return processed


async def main() -> int:
    """Main entry point."""
    logger.info("=" * 50)
    logger.info("Daf Yomi History Bot - Poll Commands")
    logger.info("=" * 50)
    logger.info(f"State directory: {STATE_DIR}")
    logger.info(f"State file: {STATE_FILE}")
    logger.info(f"State directory exists: {STATE_DIR.exists()}")

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set!")
        logger.error("Please add TELEGRAM_BOT_TOKEN to your repository secrets.")
        return 1

    # Log token presence (not the actual token)
    logger.info(f"TELEGRAM_BOT_TOKEN is set (length: {len(token)})")

    api = TelegramAPI(token)
    try:
        state = StateManager()

        # Delete any existing webhook to ensure getUpdates works
        # This is needed if a webhook was ever set on this bot
        await api.delete_webhook()

        last_id = state.get_last_update_id()
        logger.info(f"Last update ID: {last_id if last_id is not None else 'None (first run)'}")

        processed = await process_updates(api, state)

        new_last_id = state.get_last_update_id()
        logger.info(f"New last update ID: {new_last_id}")
        logger.info(f"Total commands processed: {processed}")
        logger.info("Poll completed successfully")
        return 0

    except Exception as e:
        logger.exception(f"Error processing updates: {e}")
        return 1

    finally:
        await api.close()


async def warm_cache() -> int:
    """Pre-warm the video cache for today's daf. Returns 0 on success."""
    logger.info("=" * 50)
    logger.info("Daf Yomi History Bot - Cache Warming")
    logger.info("=" * 50)

    try:
        state = StateManager()
        israel_now = datetime.now(ISRAEL_TZ)
        today_str = israel_now.strftime("%Y-%m-%d")

        # Check if already cached
        cached = state.get_cached_video(today_str)
        if cached:
            logger.info(f"Cache already warm for {today_str}: {cached.get('title')}")
            return 0

        # Fetch and cache
        logger.info(f"Warming cache for {today_str}...")
        daf = await get_todays_daf()
        video = await get_jewish_history_video(daf)

        cache_data = {
            "date": today_str,
            "title": video.title,
            "page_url": video.page_url,
            "video_url": video.video_url,
            "masechta": video.masechta,
            "daf": video.daf,
        }
        state.save_video_cache(cache_data)
        logger.info(f"Cache warmed successfully: {video.title}")
        return 0

    except ValueError as e:
        # Video not found on AllDaf.org — expected when today's video
        # hasn't been uploaded yet. Not a fatal error.
        logger.warning(f"Cache warming skipped (video not available): {e}")
        return 0

    except Exception as e:
        logger.exception(f"Error warming cache: {e}")
        return 1


if __name__ == "__main__":
    import asyncio

    # Support --warm-cache flag for pre-warming
    if len(sys.argv) > 1 and sys.argv[1] == "--warm-cache":
        sys.exit(asyncio.run(warm_cache()))
    else:
        sys.exit(asyncio.run(main()))
