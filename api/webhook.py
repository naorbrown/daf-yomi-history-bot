"""
Telegram Webhook Handler for Vercel Serverless

This handles incoming Telegram messages via webhook.
Deployed automatically to Vercel for free, always-on bot commands.
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import re
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

# Constants
ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")
TELEGRAM_API = "https://api.telegram.org/bot"
ALLDAF_BASE_URL = "https://alldaf.org"
ALLDAF_SERIES_URL = f"{ALLDAF_BASE_URL}/series/3940"
HEBCAL_API_URL = "https://www.hebcal.com/hebcal"

# Masechta name mapping
MASECHTA_NAME_MAP = {
    "Berakhot": "Berachos", "Shabbat": "Shabbos", "Sukkah": "Succah",
    "Taanit": "Taanis", "Megillah": "Megilah", "Chagigah": "Chagiga",
    "Yevamot": "Yevamos", "Ketubot": "Kesuvos", "Gittin": "Gitin",
    "Kiddushin": "Kidushin", "Bava Kamma": "Bava Kama",
    "Bava Batra": "Bava Basra", "Makkot": "Makos", "Shevuot": "Shevuos",
    "Horayot": "Horayos", "Menachot": "Menachos", "Chullin": "Chulin",
    "Bekhorot": "Bechoros", "Arakhin": "Erchin", "Keritot": "Kerisus",
    "Niddah": "Nidah",
}

# Messages
WELCOME_MESSAGE = """📚 *Welcome to Daf Yomi History Bot!*

I send you daily Jewish History videos from Dr. Henry Abramson's series on AllDaf.org, matching the Daf Yomi schedule.

*Commands:*
/today — Get today's video now
/help — Show this message

You'll automatically receive the daily video every morning at 6:00 AM Israel time.

_Enjoy your learning!_ 🎓"""

HELP_MESSAGE = """📖 *Daf Yomi History Bot - Help*

*Available Commands:*

/today — Get today's Daf Yomi history video
/help — Show this help message

*About:*
This bot sends Jewish History videos from AllDaf.org's series by Dr. Henry Abramson. Each video corresponds to the daily Daf Yomi page.

*Schedule:*
Daily videos are sent automatically at 6:00 AM Israel time.

*Questions?*
Visit: github.com/naorbrown/daf-yomi-history-bot"""


def get_bot_token():
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
        method="POST"
    )

    with urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def send_message(chat_id: int, text: str, parse_mode: str = "Markdown") -> dict:
    """Send a text message."""
    return telegram_api_call("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    })


def send_video(chat_id: int, video_url: str, caption: str) -> dict:
    """Send a video."""
    return telegram_api_call("sendVideo", {
        "chat_id": chat_id,
        "video": video_url,
        "caption": caption,
        "parse_mode": "Markdown",
        "supports_streaming": True,
    })


def fetch_url(url: str) -> str:
    """Fetch URL content."""
    req = Request(url, headers={"User-Agent": "DafYomiBot/1.0"})
    with urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8")


def get_todays_daf() -> tuple:
    """Get today's daf from Hebcal API. Returns (masechta, daf)."""
    israel_now = datetime.now(ISRAEL_TZ)
    today_str = israel_now.strftime("%Y-%m-%d")

    params = urlencode({
        "v": "1", "cfg": "json", "F": "on",
        "start": today_str, "end": today_str,
    })

    data = json.loads(fetch_url(f"{HEBCAL_API_URL}?{params}"))

    for item in data.get("items", []):
        if item.get("category") == "dafyomi":
            title = item.get("title", "")
            match = re.match(r"(.+)\s+(\d+)", title)
            if match:
                hebcal_name = match.group(1)
                daf = int(match.group(2))
                alldaf_name = MASECHTA_NAME_MAP.get(hebcal_name, hebcal_name)
                return (alldaf_name, daf)

    raise ValueError(f"No Daf Yomi found for {today_str}")


def get_video_info(masechta: str, daf: int) -> dict:
    """Find the Jewish History video for a daf."""
    masechta_lower = masechta.lower()

    # Fetch series page
    html = fetch_url(ALLDAF_SERIES_URL)

    # Find video link
    page_url = None
    title = None

    # Simple regex to find links (avoiding BeautifulSoup dependency)
    link_pattern = r'<a[^>]+href="(/p/[^"]+)"[^>]*>([^<]+)</a>'
    for match in re.finditer(link_pattern, html, re.IGNORECASE):
        href, link_text = match.groups()
        link_text_lower = link_text.lower().strip()

        if masechta_lower not in link_text_lower:
            continue

        # Check for daf number
        if (f"{masechta_lower} {daf}" in link_text_lower or
            re.search(rf"{masechta_lower}\s+{daf}\b", link_text_lower)):
            page_url = f"{ALLDAF_BASE_URL}{href}"
            title = link_text.strip()
            break

    if not page_url:
        raise ValueError(f"Video not found for {masechta} {daf}")

    # Fetch video page for MP4 URL
    video_html = fetch_url(page_url)

    video_url = None
    mp4_match = re.search(
        r"https://(?:cdn\.jwplayer\.com|content\.jwplatform\.com)/videos/([a-zA-Z0-9]+)\.mp4",
        video_html
    )
    if mp4_match:
        video_url = f"https://cdn.jwplayer.com/videos/{mp4_match.group(1)}.mp4"

    return {
        "title": title,
        "page_url": page_url,
        "video_url": video_url,
        "masechta": masechta,
        "daf": daf,
    }


def handle_today_command(chat_id: int) -> None:
    """Handle /today command."""
    try:
        # Send loading message
        loading = send_message(chat_id, "🔍 Finding today's Daf Yomi history video...")
        loading_id = loading.get("result", {}).get("message_id")

        # Get today's daf
        masechta, daf = get_todays_daf()

        # Get video info
        video = get_video_info(masechta, daf)

        # Delete loading message
        if loading_id:
            try:
                telegram_api_call("deleteMessage", {
                    "chat_id": chat_id,
                    "message_id": loading_id,
                })
            except:
                pass

        # Format caption
        caption = (
            f"📚 *Today's Daf Yomi History*\n\n"
            f"*{video['masechta']} {video['daf']}*\n"
            f"{video['title']}"
        )

        if video["video_url"]:
            send_video(chat_id, video["video_url"], caption)
        else:
            message = f"{caption}\n\n[Watch the video]({video['page_url']})"
            send_message(chat_id, message)

    except Exception as e:
        send_message(
            chat_id,
            f"Sorry, I couldn't find today's video. Please try again later.\n\n"
            f"You can also visit AllDaf.org directly:\n"
            f"https://alldaf.org/series/3940"
        )


def process_update(update: dict) -> None:
    """Process a Telegram update."""
    message = update.get("message", {})
    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")

    if not chat_id:
        return

    # Handle commands
    if text.startswith("/start"):
        send_message(chat_id, WELCOME_MESSAGE)
    elif text.startswith("/help"):
        send_message(chat_id, HELP_MESSAGE)
    elif text.startswith("/today"):
        handle_today_command(chat_id)


class handler(BaseHTTPRequestHandler):
    """Vercel serverless function handler."""

    def do_POST(self):
        """Handle POST request from Telegram webhook."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            update = json.loads(body.decode("utf-8"))

            process_update(update)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

        except Exception as e:
            self.send_response(200)  # Always return 200 to Telegram
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

    def do_GET(self):
        """Health check endpoint."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "ok", "bot": "Daf Yomi History Bot"}')
