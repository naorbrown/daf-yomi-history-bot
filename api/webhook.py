"""
Telegram Webhook Handler for Vercel Serverless

Handles incoming Telegram messages via webhook for bot commands.
Deployed to Vercel for always-on, serverless bot responses.
"""

from http.server import BaseHTTPRequestHandler
import json
import logging
import os
import re
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import URLError, HTTPError
from zoneinfo import ZoneInfo

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Constants
ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")
TELEGRAM_API = "https://api.telegram.org/bot"
ALLDAF_BASE_URL = "https://alldaf.org"
ALLDAF_SERIES_URL = f"{ALLDAF_BASE_URL}/series/3940"
HEBCAL_API_URL = "https://www.hebcal.com/hebcal"
REQUEST_TIMEOUT = 30

# Masechta name mapping: Hebcal -> AllDaf format
MASECHTA_NAME_MAP = {
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

# Bot messages
WELCOME_MESSAGE = (
    "📚 *Welcome to Daf Yomi History Bot!*\n\n"
    "I send you daily Jewish History videos from Dr. Henry Abramson's series "
    "on AllDaf.org, matching the Daf Yomi schedule.\n\n"
    "*Commands:*\n"
    "/today — Get today's video now\n"
    "/help — Show this message\n\n"
    "You'll automatically receive the daily video every morning at "
    "6:00 AM Israel time.\n\n"
    "_Enjoy your learning!_ 🎓"
)

HELP_MESSAGE = (
    "📖 *Daf Yomi History Bot - Help*\n\n"
    "*Available Commands:*\n\n"
    "/today — Get today's Daf Yomi history video\n"
    "/help — Show this help message\n\n"
    "*About:*\n"
    "This bot sends Jewish History videos from AllDaf.org's series "
    "by Dr. Henry Abramson. Each video corresponds to the daily Daf Yomi page.\n\n"
    "*Schedule:*\n"
    "Daily videos are sent automatically at 6:00 AM Israel time."
)

ERROR_MESSAGE = """Sorry, I couldn't find today's video. Please try again later.

You can also visit AllDaf.org directly:
https://alldaf.org/series/3940"""


def get_bot_token() -> str:
    """Get bot token from environment."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set")
    return token


def telegram_api_call(method: str, data: dict) -> dict:
    """Make a Telegram Bot API call."""
    token = get_bot_token()
    url = f"{TELEGRAM_API}{token}/{method}"

    req = Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except (URLError, HTTPError) as e:
        logger.error(f"Telegram API error for {method}: {e}")
        raise


def send_message(chat_id: int, text: str, parse_mode: str = "Markdown") -> dict:
    """Send a text message to a chat."""
    return telegram_api_call(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        },
    )


def send_video(chat_id: int, video_url: str, caption: str) -> dict:
    """Send a video to a chat."""
    return telegram_api_call(
        "sendVideo",
        {
            "chat_id": chat_id,
            "video": video_url,
            "caption": caption,
            "parse_mode": "Markdown",
            "supports_streaming": True,
        },
    )


def delete_message(chat_id: int, message_id: int) -> None:
    """Delete a message (silently ignore errors)."""
    try:
        telegram_api_call(
            "deleteMessage",
            {"chat_id": chat_id, "message_id": message_id},
        )
    except Exception:
        pass  # Ignore delete errors


def fetch_url(url: str) -> str:
    """Fetch URL content with proper headers."""
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; DafYomiBot/1.0)",
            "Accept": "text/html,application/json",
        },
    )
    try:
        with urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            return response.read().decode("utf-8")
    except (URLError, HTTPError) as e:
        logger.error(f"Failed to fetch {url}: {e}")
        raise


def get_todays_daf() -> tuple[str, int]:
    """
    Get today's Daf Yomi from Hebcal API.

    Returns:
        Tuple of (masechta_name, daf_number)
    """
    israel_now = datetime.now(ISRAEL_TZ)
    today_str = israel_now.strftime("%Y-%m-%d")

    params = urlencode({
        "v": "1",
        "cfg": "json",
        "F": "on",
        "start": today_str,
        "end": today_str,
    })

    url = f"{HEBCAL_API_URL}?{params}"
    logger.info(f"Fetching daf from Hebcal: {today_str}")

    data = json.loads(fetch_url(url))

    for item in data.get("items", []):
        if item.get("category") == "dafyomi":
            title = item.get("title", "")
            match = re.match(r"(.+)\s+(\d+)", title)
            if match:
                hebcal_name = match.group(1)
                daf = int(match.group(2))
                alldaf_name = MASECHTA_NAME_MAP.get(hebcal_name, hebcal_name)
                logger.info(f"Today's daf: {alldaf_name} {daf}")
                return (alldaf_name, daf)

    raise ValueError(f"No Daf Yomi found for {today_str}")


def get_video_info(masechta: str, daf: int) -> dict:
    """
    Find the Jewish History video for a specific daf.

    Returns:
        Dict with title, page_url, video_url, masechta, daf
    """
    masechta_lower = masechta.lower()
    logger.info(f"Searching for video: {masechta} {daf}")

    # Fetch series page
    html = fetch_url(ALLDAF_SERIES_URL)

    # Find video link - try multiple patterns
    page_url = None
    title = None

    # Pattern 1: Standard anchor tags with href
    link_pattern = r'<a[^>]+href="(/p/[^"]+)"[^>]*>([^<]+)</a>'
    for match in re.finditer(link_pattern, html, re.IGNORECASE | re.DOTALL):
        href, link_text = match.groups()
        link_text = link_text.strip()
        link_text_lower = link_text.lower()

        if masechta_lower not in link_text_lower:
            continue

        # Check for exact daf match
        patterns = [
            rf"\b{masechta_lower}\s+{daf}\b",
            rf"\b{masechta_lower}\s+daf\s+{daf}\b",
        ]

        if any(re.search(p, link_text_lower) for p in patterns):
            page_url = f"{ALLDAF_BASE_URL}{href}"
            title = link_text
            logger.info(f"Found video: {title} at {page_url}")
            break

    if not page_url:
        raise ValueError(f"Video not found for {masechta} {daf}")

    # Fetch video page to extract MP4 URL
    video_html = fetch_url(page_url)

    video_url = None
    mp4_pattern = (
        r"https://(?:cdn\.jwplayer\.com|content\.jwplatform\.com)"
        r"/videos/([a-zA-Z0-9]+)\.mp4"
    )
    mp4_match = re.search(mp4_pattern, video_html)
    if mp4_match:
        video_url = f"https://cdn.jwplayer.com/videos/{mp4_match.group(1)}.mp4"
        logger.info(f"Found video URL: {video_url}")
    else:
        logger.warning("Could not extract direct video URL")

    return {
        "title": title,
        "page_url": page_url,
        "video_url": video_url,
        "masechta": masechta,
        "daf": daf,
    }


def handle_today_command(chat_id: int) -> None:
    """Handle the /today command - fetch and send today's video."""
    loading_msg_id = None

    try:
        # Send loading message
        result = send_message(chat_id, "🔍 Finding today's Daf Yomi history video...")
        loading_msg_id = result.get("result", {}).get("message_id")

        # Get today's daf
        masechta, daf = get_todays_daf()

        # Get video info
        video = get_video_info(masechta, daf)

        # Delete loading message
        if loading_msg_id:
            delete_message(chat_id, loading_msg_id)

        # Format caption
        caption = (
            f"📚 *Today's Daf Yomi History*\n\n"
            f"*{video['masechta']} {video['daf']}*\n"
            f"{video['title']}\n\n"
            f"[View on AllDaf.org]({video['page_url']})"
        )

        # Send video or text
        if video.get("video_url"):
            send_video(chat_id, video["video_url"], caption)
        else:
            send_message(chat_id, caption)

        logger.info(f"Sent video to chat {chat_id}: {video['title']}")

    except Exception as e:
        logger.error(f"Error in /today command: {e}")

        # Delete loading message if it exists
        if loading_msg_id:
            delete_message(chat_id, loading_msg_id)

        # Send error message
        send_message(chat_id, ERROR_MESSAGE, parse_mode=None)


def process_update(update: dict) -> None:
    """Process a Telegram update (message)."""
    message = update.get("message", {})
    text = message.get("text", "").strip()
    chat = message.get("chat", {})
    chat_id = chat.get("id")

    if not chat_id or not text:
        return

    logger.info(f"Received command from chat {chat_id}: {text}")

    # Handle commands
    command = text.split()[0].lower() if text else ""

    if command in ("/start", "/start@dafhistorybot"):
        send_message(chat_id, WELCOME_MESSAGE)
    elif command in ("/help", "/help@dafhistorybot"):
        send_message(chat_id, HELP_MESSAGE)
    elif command in ("/today", "/today@dafhistorybot"):
        handle_today_command(chat_id)


class handler(BaseHTTPRequestHandler):
    """Vercel serverless function handler."""

    def log_message(self, format, *args):
        """Override to use our logger."""
        logger.info("%s - %s", self.address_string(), format % args)

    def do_POST(self):
        """Handle POST request from Telegram webhook."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            update = json.loads(body.decode("utf-8"))

            logger.info(f"Received webhook update: {update.get('update_id')}")
            process_update(update)

        except Exception as e:
            logger.error(f"Webhook error: {e}")

        # Always return 200 to Telegram (prevents retries)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true}')

    def do_GET(self):
        """Health check endpoint."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        response = {
            "status": "ok",
            "bot": "Daf Yomi History Bot",
            "version": "2.0.0",
        }
        self.wfile.write(json.dumps(response).encode("utf-8"))
