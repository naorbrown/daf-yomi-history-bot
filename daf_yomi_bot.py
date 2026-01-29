#!/usr/bin/env python3
"""
Daf Yomi History Bot - APScheduler Version

Alternative scheduler-based bot that sends the daily Daf Yomi Jewish History
video from AllDaf.org every morning at 6:00 AM Israel time.

This is an alternative to the GitHub Actions-based scheduler (send_video.py).
Use this for self-hosted deployments where you want a long-running process.

For serverless deployment, use GitHub Actions (send_video.py) instead.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from bs4 import BeautifulSoup
from telegram import Bot

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Configuration from environment
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Constants
ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")
ALLDAF_BASE_URL = "https://alldaf.org"
ALLDAF_SERIES_URL = f"{ALLDAF_BASE_URL}/series/3940"
HEBCAL_API_URL = "https://www.hebcal.com/hebcal"
REQUEST_TIMEOUT = 30.0

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


def convert_masechta_name(name: str) -> str:
    """Convert Hebcal masechta name to AllDaf format."""
    return MASECHTA_NAME_MAP.get(name, name)


async def get_todays_daf() -> dict:
    """
    Fetch today's daf from Hebcal API using Israel date.

    Returns:
        Dict with masechta and daf number
    """
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
                    return {"masechta": alldaf_masechta, "daf": daf}

        raise ValueError(f"No Daf Yomi found for {today_str}")


async def get_jewish_history_video(masechta: str, daf: int) -> dict:
    """
    Find the Jewish History video for a specific daf.

    Returns:
        Dict with title, page_url, video_url, masechta, daf
    """
    masechta_lower = masechta.lower()

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
                rf"\b{masechta_lower}\s+{daf}\b",
                rf"\b{masechta_lower}\s+daf\s+{daf}\b",
            ]

            if any(re.search(p, link_text_lower) for p in patterns):
                page_url = f"{ALLDAF_BASE_URL}{href}"
                title = link_text
                logger.info(f"Found video: {title}")
                break

        if not page_url:
            raise ValueError(f"Video not found for {masechta} {daf}")

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
        else:
            logger.warning("Could not find direct video URL")

        return {
            "title": title,
            "page_url": page_url,
            "video_url": video_url,
            "masechta": masechta,
            "daf": daf,
        }


async def send_daily_video() -> None:
    """Fetch and send the daily Jewish History video."""
    try:
        logger.info("Starting daily video fetch...")

        # Get today's daf
        daf_info = await get_todays_daf()

        # Get the Jewish History video
        video = await get_jewish_history_video(daf_info["masechta"], daf_info["daf"])

        # Format caption
        caption = (
            f"📚 *Today's Daf Yomi History*\n\n"
            f"*{video['masechta']} {video['daf']}*\n"
            f"{video['title']}\n\n"
            f"[View on AllDaf.org]({video['page_url']})"
        )

        # Send via Telegram
        bot = Bot(token=TELEGRAM_BOT_TOKEN)

        if video.get("video_url"):
            logger.info(f"Sending video: {video['video_url']}")
            await bot.send_video(
                chat_id=TELEGRAM_CHAT_ID,
                video=video["video_url"],
                caption=caption,
                parse_mode="Markdown",
                supports_streaming=True,
            )
        else:
            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=caption,
                parse_mode="Markdown",
                disable_web_page_preview=False,
            )

        logger.info("Message sent successfully!")

    except Exception as e:
        logger.error(f"Error sending daily video: {e}")
        try:
            bot = Bot(token=TELEGRAM_BOT_TOKEN)
            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=f"Error fetching today's Daf Yomi History video: {e}",
            )
        except Exception:
            pass


async def main() -> None:
    """Main entry point - sets up scheduler and runs the bot."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")
    if not TELEGRAM_CHAT_ID:
        raise ValueError("TELEGRAM_CHAT_ID environment variable not set")

    logger.info("Starting Daf Yomi History Bot (APScheduler mode)...")

    # Create scheduler
    scheduler = AsyncIOScheduler(timezone=ISRAEL_TZ)

    # Schedule daily job at 6:00 AM Israel time
    scheduler.add_job(
        send_daily_video,
        CronTrigger(hour=6, minute=0, timezone=ISRAEL_TZ),
        id="daily_daf_video",
        name="Send daily Daf Yomi History video",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started. Daily video will be sent at 6:00 AM Israel time.")

    # Keep running
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
