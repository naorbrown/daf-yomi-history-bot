#!/usr/bin/env python3
"""
Daf Yomi History Bot - Interactive Telegram Bot

A friendly Telegram bot that sends Jewish History videos from AllDaf.org.
Responds to user commands and sends daily videos automatically.

Commands:
    /start  - Welcome message and instructions
    /today  - Get today's Daf Yomi history video
    /help   - Show available commands
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

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

# Masechta name mapping
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

# Messages
WELCOME_MESSAGE = """
📚 *Welcome to Daf Yomi History Bot!*

I send you daily Jewish History videos from Dr. Henry Abramson's series on AllDaf.org, matching the Daf Yomi schedule.

*Commands:*
/today — Get today's video now
/help — Show this message

You'll automatically receive the daily video at 1:30 AM Israel time.

_Enjoy your learning!_ 🎓
"""

HELP_MESSAGE = """
📖 *Daf Yomi History Bot - Help*

*Available Commands:*

/today — Get today's Daf Yomi history video
/help — Show this help message

*About:*
This bot sends Jewish History videos from AllDaf.org's series by Dr. Henry Abramson. Each video corresponds to the daily Daf Yomi page.

*Schedule:*
Daily videos are sent automatically at 1:30 AM Israel time.

*Questions?*
Visit: github.com/naorbrown/daf-yomi-history-bot
"""


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
            raise ValueError(
                f"Could not find video for {daf.masechta} {daf.daf}"
            )

        response = await client.get(page_url)
        response.raise_for_status()

        video_url = None
        mp4_pattern = r"https://(?:cdn\.jwplayer\.com|content\.jwplatform\.com)/videos/([a-zA-Z0-9]+)\.mp4"
        mp4_match = re.search(mp4_pattern, response.text)

        if mp4_match:
            video_url = f"https://cdn.jwplayer.com/videos/{mp4_match.group(1)}.mp4"

        return VideoInfo(
            title=title,
            page_url=page_url,
            video_url=video_url,
            masechta=daf.masechta,
            daf=daf.daf,
        )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    await update.message.reply_text(
        WELCOME_MESSAGE,
        parse_mode="Markdown",
    )
    logger.info(f"New user started bot: {update.effective_user.id}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /help command."""
    await update.message.reply_text(
        HELP_MESSAGE,
        parse_mode="Markdown",
    )


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /today command - send today's video."""
    chat_id = update.effective_chat.id

    # Send "loading" message
    loading_msg = await update.message.reply_text(
        "🔍 Finding today's Daf Yomi history video..."
    )

    try:
        # Get today's daf
        daf = await get_todays_daf()

        # Find the video
        video = await get_jewish_history_video(daf)

        # Delete loading message
        await loading_msg.delete()

        # Format caption
        caption = (
            f"📚 *Today's Daf Yomi History*\n\n"
            f"*{video.masechta} {video.daf}*\n"
            f"{video.title}"
        )

        if video.video_url:
            await context.bot.send_video(
                chat_id=chat_id,
                video=video.video_url,
                caption=caption,
                parse_mode="Markdown",
                supports_streaming=True,
            )
        else:
            message = f"{caption}\n\n[Watch the video]({video.page_url})"
            await context.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode="Markdown",
                disable_web_page_preview=False,
            )

        logger.info(f"Sent video to user {update.effective_user.id}: {video.title}")

    except Exception as e:
        logger.error(f"Error in /today command: {e}")
        await loading_msg.edit_text(
            f"Sorry, I couldn't find today's video. Please try again later.\n\n"
            f"You can also visit AllDaf.org directly:\n"
            f"https://alldaf.org/series/3940"
        )


def main() -> None:
    """Start the bot."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")

    # Create application
    application = Application.builder().token(token).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("today", today_command))

    # Start the bot
    logger.info("Starting Daf Yomi History Bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
