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

I send you daily Jewish History videos from Dr. Henry Abramson's series on AllDaf.org, matching the Daf Yomi schedule.

Commands:
/today - Get today's video now
/help - Show this message

You'll automatically receive the daily video every morning at 6:00 AM Israel time.

Enjoy your learning!"""

HELP_MESSAGE = """Daf Yomi History Bot - Help

Available Commands:

/today - Get today's Daf Yomi history video
/help - Show this help message

About:
This bot sends Jewish History videos from AllDaf.org's series by Dr. Henry Abramson. Each video corresponds to the daily Daf Yomi page.

Schedule:
Daily videos are sent automatically at 6:00 AM Israel time.

Note: Commands are processed every 5 minutes."""

ERROR_MESSAGE = """Sorry, I couldn't find today's video. Please try again later.

You can also visit AllDaf.org directly:
https://alldaf.org/series/3940"""

RATE_LIMITED_MESSAGE = (
    """You're sending too many requests. Please wait a minute and try again."""
)


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
    """Simple Telegram Bot API client."""

    def __init__(self, token: str):
        self.token = token
        self.base_url = f"{TELEGRAM_API_BASE}{token}"

    async def get_updates(self, offset: Optional[int] = None) -> list[dict[str, Any]]:
        """Fetch new updates from Telegram."""
        params = {"timeout": 0, "allowed_updates": ["message"]}
        if offset:
            params["offset"] = offset

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(f"{self.base_url}/getUpdates", params=params)
            response.raise_for_status()
            data = response.json()

            if not data.get("ok"):
                raise RuntimeError(f"Telegram API error: {data}")

            return data.get("result", [])

    async def send_message(self, chat_id: int, text: str) -> dict[str, Any]:
        """Send a text message."""
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(
                f"{self.base_url}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )
            response.raise_for_status()
            return response.json()

    async def send_video(
        self, chat_id: int, video_url: str, caption: str
    ) -> dict[str, Any]:
        """Send a video message."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/sendVideo",
                json={
                    "chat_id": chat_id,
                    "video": video_url,
                    "caption": caption,
                    "supports_streaming": True,
                },
            )
            response.raise_for_status()
            return response.json()


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


async def get_jewish_history_video(daf: DafInfo) -> VideoInfo:
    """Find the Jewish History video for a specific daf."""
    masechta_lower = daf.masechta.lower()

    async with httpx.AsyncClient(
        follow_redirects=True, timeout=REQUEST_TIMEOUT
    ) as client:
        response = await client.get(ALLDAF_SERIES_URL)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

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
                rf"\b{masechta_lower}\s+{daf.daf}\b",
                rf"\b{masechta_lower}\s+daf\s+{daf.daf}\b",
            ]

            if any(re.search(p, link_text_lower) for p in patterns):
                page_url = f"{ALLDAF_BASE_URL}{href}"
                title = link_text
                logger.info(f"Found video: {title}")
                break

        if not page_url:
            raise ValueError(f"Video not found for {daf.masechta} {daf.daf}")

        # Fetch video page for MP4 URL
        response = await client.get(page_url)
        response.raise_for_status()

        video_url = None
        mp4_pattern = (
            r"https://(?:cdn\.jwplayer\.com|content\.jwplatform\.com)"
            r"/videos/([a-zA-Z0-9]+)\.mp4"
        )
        mp4_match = re.search(mp4_pattern, response.text)

        if mp4_match:
            video_url = f"https://cdn.jwplayer.com/videos/{mp4_match.group(1)}.mp4"
            logger.info(f"Found video URL: {video_url}")

        return VideoInfo(
            title=title,
            page_url=page_url,
            video_url=video_url,
            masechta=daf.masechta,
            daf=daf.daf,
        )


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


async def handle_command(
    api: TelegramAPI,
    chat_id: int,
    command: str,
    rate_limiter: RateLimiter,
    user_id: int,
) -> None:
    """Handle a bot command."""
    # Rate limit check (except for start)
    if command != "start" and not rate_limiter.is_allowed(user_id):
        await api.send_message(chat_id, RATE_LIMITED_MESSAGE)
        logger.info(f"Rate limited user {user_id}")
        return

    if command == "start":
        await api.send_message(chat_id, WELCOME_MESSAGE)
        logger.info(f"Sent welcome to user {user_id}")

    elif command == "help":
        await api.send_message(chat_id, HELP_MESSAGE)
        logger.info(f"Sent help to user {user_id}")

    elif command == "today":
        try:
            daf = await get_todays_daf()
            video = await get_jewish_history_video(daf)

            caption = (
                f"Today's Daf Yomi History\n\n"
                f"{video.masechta} {video.daf}\n"
                f"{video.title}\n\n"
                f"View on AllDaf.org: {video.page_url}"
            )

            if video.video_url:
                await api.send_video(chat_id, video.video_url, caption)
            else:
                await api.send_message(chat_id, caption)

            logger.info(f"Sent video to user {user_id}: {video.title}")

        except Exception as e:
            logger.error(f"Error fetching video: {e}")
            await api.send_message(chat_id, ERROR_MESSAGE)

    else:
        # Unknown command - ignore silently
        logger.debug(f"Unknown command: {command}")


async def process_updates(api: TelegramAPI, state: StateManager) -> int:
    """Process pending Telegram updates. Returns count of processed updates."""
    last_update_id = state.get_last_update_id()
    offset = last_update_id + 1 if last_update_id else None

    updates = await api.get_updates(offset)
    if not updates:
        logger.info("No new updates")
        return 0

    rate_limiter = RateLimiter(state)
    processed = 0

    for update in updates:
        update_id = update.get("update_id")
        message = update.get("message", {})
        text = message.get("text")
        chat_id = message.get("chat", {}).get("id")
        user_id = message.get("from", {}).get("id")

        if not chat_id or not user_id:
            logger.warning(f"Skipping update {update_id}: missing chat_id or user_id")
            state.set_last_update_id(update_id)
            continue

        command = parse_command(text)
        if command:
            logger.info(f"Processing command /{command} from user {user_id}")
            await handle_command(api, chat_id, command, rate_limiter, user_id)
            processed += 1

        # Always update the offset, even for non-command messages
        state.set_last_update_id(update_id)

    logger.info(f"Processed {processed} command(s) from {len(updates)} update(s)")
    return processed


async def main() -> int:
    """Main entry point."""
    logger.info("=" * 50)
    logger.info("Daf Yomi History Bot - Poll Commands")
    logger.info("=" * 50)
    logger.info(f"State directory: {STATE_DIR}")
    logger.info(f"State file: {STATE_FILE}")

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set")
        return 1

    try:
        api = TelegramAPI(token)
        state = StateManager()

        last_id = state.get_last_update_id()
        logger.info(f"Last update ID: {last_id or 'None (first run)'}")

        processed = await process_updates(api, state)

        new_last_id = state.get_last_update_id()
        logger.info(f"New last update ID: {new_last_id}")
        logger.info(f"Total commands processed: {processed}")
        logger.info("Poll completed successfully")
        return 0

    except Exception as e:
        logger.exception(f"Error processing updates: {e}")
        return 1


if __name__ == "__main__":
    import asyncio

    sys.exit(asyncio.run(main()))
