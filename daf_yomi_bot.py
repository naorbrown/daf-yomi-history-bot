#!/usr/bin/env python3
"""
Daf Yomi History Telegram Bot

Sends the daily Daf Yomi Jewish History video from alldaf.org
every morning at 6:00 AM Israel time.
"""

import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup
from telegram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration - Set these environment variables
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# Israel timezone
ISRAEL_TZ = ZoneInfo('Asia/Jerusalem')

# URLs
ALLDAF_BASE_URL = "https://alldaf.org"

# Mapping from Hebcal masechta names to AllDaf names
MASECHTA_MAP = {
    'Berakhot': 'Berachos',
    'Shabbat': 'Shabbos',
    'Sukkah': 'Succah',
    'Taanit': 'Taanis',
    'Megillah': 'Megilah',
    'Chagigah': 'Chagiga',
    'Yevamot': 'Yevamos',
    'Ketubot': 'Kesuvos',
    'Gittin': 'Gitin',
    'Kiddushin': 'Kidushin',
    'Bava Kamma': 'Bava Kama',
    'Bava Batra': 'Bava Basra',
    'Makkot': 'Makos',
    'Shevuot': 'Shevuos',
    'Horayot': 'Horayos',
    'Menachot': 'Menachos',
    'Chullin': 'Chulin',
    'Bekhorot': 'Bechoros',
    'Arakhin': 'Erchin',
    'Keritot': 'Kerisus',
    'Niddah': 'Nidah',
}


def convert_masechta_name(name: str) -> str:
    """Convert Hebcal masechta name to AllDaf format."""
    return MASECHTA_MAP.get(name, name)


async def get_todays_daf_info() -> dict:
    """
    Fetch today's daf information from Hebcal API using Israel date.
    Returns dict with masechta and daf number.
    """
    # Get today's date in Israel timezone
    israel_now = datetime.now(ISRAEL_TZ)
    today_str = israel_now.strftime('%Y-%m-%d')

    # Hebcal API for Daf Yomi
    hebcal_url = f"https://www.hebcal.com/hebcal?v=1&cfg=json&F=on&start={today_str}&end={today_str}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(hebcal_url)
        response.raise_for_status()
        data = response.json()

        # Find Daf Yomi entry
        for item in data.get('items', []):
            if item.get('category') == 'dafyomi':
                # Parse "Menachot 16" format
                title = item.get('title', '')
                match = re.match(r'(.+)\s+(\d+)', title)
                if match:
                    hebcal_masechta = match.group(1)
                    daf = int(match.group(2))
                    alldaf_masechta = convert_masechta_name(hebcal_masechta)
                    return {
                        'masechta': alldaf_masechta,
                        'daf': daf,
                        'hebcal_name': hebcal_masechta
                    }

        raise ValueError(f"Could not find Daf Yomi in Hebcal for {today_str}")


async def get_jewish_history_video(masechta: str, daf: int) -> dict:
    """
    Find the Jewish History in Daf Yomi video for a specific daf.
    Returns dict with title, page URL, and direct video URL.
    """
    # Try the Jewish History series page with search
    series_url = f"{ALLDAF_BASE_URL}/series/3940"

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        response = await client.get(series_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Normalize masechta name for comparison
        masechta_lower = masechta.lower()
        page_url = None
        title = None

        # Look for videos matching this masechta and daf
        for link in soup.find_all('a', href=True):
            link_text = link.get_text().strip()
            link_text_lower = link_text.lower()
            href = link['href']

            if not href.startswith('/p/'):
                continue

            # Check if this matches our masechta and daf
            # Handle various formats: "Menachos 15", "Menachos Daf 15", etc.
            if masechta_lower in link_text_lower:
                # Check for daf number
                daf_patterns = [
                    f"{masechta_lower} {daf}",
                    f"{masechta_lower} daf {daf}",
                    f"{masechta_lower}{daf}",
                ]
                if any(p in link_text_lower for p in daf_patterns) or \
                   re.search(rf'{masechta_lower}\s+{daf}\b', link_text_lower):
                    page_url = f"{ALLDAF_BASE_URL}{href}"
                    title = link_text
                    break

        # If not found on series page, try the daf page directly
        if not page_url:
            daf_page_url = f"{ALLDAF_BASE_URL}/?masechta={masechta}&daf={daf}"
            logger.info(f"Trying daf page: {daf_page_url}")

            response = await client.get(daf_page_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Look for Jewish History video in supplemental clips
            for link in soup.find_all('a', href=True):
                href = link['href']
                if not href.startswith('/p/'):
                    continue

                # Check parent context for Jewish History indicators
                parent = link.find_parent(['div', 'li', 'section'])
                if parent:
                    parent_text = parent.get_text().lower()
                    if 'jewish history' in parent_text or 'abramson' in parent_text or 'henry' in parent_text:
                        link_text = link.get_text().strip()
                        if link_text and masechta_lower in link_text.lower():
                            page_url = f"{ALLDAF_BASE_URL}{href}"
                            title = link_text
                            break

        if not page_url:
            raise ValueError(f"Could not find Jewish History video for {masechta} {daf}")

        # Now fetch the video page to get the direct MP4 URL
        logger.info(f"Fetching video page: {page_url}")
        response = await client.get(page_url)
        response.raise_for_status()

        # Extract the JWPlayer video URL
        video_url = None

        # Look for mp4 URL patterns
        mp4_match = re.search(r'https://(?:cdn\.jwplayer\.com|content\.jwplatform\.com)/videos/([a-zA-Z0-9]+)\.mp4', response.text)
        if mp4_match:
            video_url = f"https://cdn.jwplayer.com/videos/{mp4_match.group(1)}.mp4"

        if not video_url:
            logger.warning(f"Could not find direct video URL, falling back to page URL")

        return {
            'title': title,
            'page_url': page_url,
            'video_url': video_url,
            'masechta': masechta,
            'daf': daf
        }


async def send_daily_video():
    """
    Main function to fetch and send the daily Jewish History video.
    """
    try:
        logger.info("Starting daily video fetch...")

        # Get today's daf
        daf_info = await get_todays_daf_info()
        logger.info(f"Today's daf: {daf_info['masechta']} {daf_info['daf']}")

        # Get the Jewish History video
        video_info = await get_jewish_history_video(daf_info['masechta'], daf_info['daf'])
        logger.info(f"Found video: {video_info['title']}")

        # Format caption
        caption = (
            f"📚 *Today's Daf Yomi History*\n\n"
            f"*{video_info['masechta']} {video_info['daf']}*\n"
            f"{video_info['title']}"
        )

        # Send via Telegram
        bot = Bot(token=TELEGRAM_BOT_TOKEN)

        if video_info.get('video_url'):
            # Send the video directly embedded
            logger.info(f"Sending video: {video_info['video_url']}")
            await bot.send_video(
                chat_id=TELEGRAM_CHAT_ID,
                video=video_info['video_url'],
                caption=caption,
                parse_mode='Markdown',
                supports_streaming=True
            )
        else:
            # Fallback to sending a link if we couldn't get the video URL
            message = f"{caption}\n\n[Watch the video]({video_info['page_url']})"
            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=message,
                parse_mode='Markdown',
                disable_web_page_preview=False
            )

        logger.info("Message sent successfully!")

    except Exception as e:
        logger.error(f"Error sending daily video: {e}")
        # Try to notify about the error
        try:
            bot = Bot(token=TELEGRAM_BOT_TOKEN)
            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=f"Error fetching today's Daf Yomi History video: {str(e)}"
            )
        except:
            pass


async def main():
    """
    Main entry point - sets up scheduler and runs the bot.
    """
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")
    if not TELEGRAM_CHAT_ID:
        raise ValueError("TELEGRAM_CHAT_ID environment variable not set")

    logger.info("Starting Daf Yomi History Bot...")

    # Create scheduler
    scheduler = AsyncIOScheduler(timezone=ISRAEL_TZ)

    # Schedule daily job at 6:00 AM Israel time
    scheduler.add_job(
        send_daily_video,
        CronTrigger(hour=6, minute=0, timezone=ISRAEL_TZ),
        id='daily_daf_video',
        name='Send daily Daf Yomi History video',
        replace_existing=True
    )

    scheduler.start()
    logger.info("Scheduler started. Daily video will be sent at 6:00 AM Israel time.")

    # Keep the bot running
    try:
        while True:
            await asyncio.sleep(3600)  # Sleep for an hour
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Bot stopped.")


if __name__ == '__main__':
    asyncio.run(main())
