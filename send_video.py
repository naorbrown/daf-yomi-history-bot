#!/usr/bin/env python3
"""
Send Daily Daf Yomi History Video

Simplified script for GitHub Actions - sends the video once and exits.
"""

import asyncio
import logging
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup
from telegram import Bot

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
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
    """Fetch today's daf from Hebcal API using Israel date."""
    israel_now = datetime.now(ISRAEL_TZ)
    today_str = israel_now.strftime('%Y-%m-%d')

    hebcal_url = f"https://www.hebcal.com/hebcal?v=1&cfg=json&F=on&start={today_str}&end={today_str}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(hebcal_url)
        response.raise_for_status()
        data = response.json()

        for item in data.get('items', []):
            if item.get('category') == 'dafyomi':
                title = item.get('title', '')
                match = re.match(r'(.+)\s+(\d+)', title)
                if match:
                    hebcal_masechta = match.group(1)
                    daf = int(match.group(2))
                    alldaf_masechta = convert_masechta_name(hebcal_masechta)
                    return {
                        'masechta': alldaf_masechta,
                        'daf': daf
                    }

        raise ValueError(f"Could not find Daf Yomi in Hebcal for {today_str}")


async def get_jewish_history_video(masechta: str, daf: int) -> dict:
    """Find the Jewish History video for a specific daf."""
    series_url = f"{ALLDAF_BASE_URL}/series/3940"

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        response = await client.get(series_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
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

            if masechta_lower in link_text_lower:
                daf_patterns = [
                    f"{masechta_lower} {daf}",
                    f"{masechta_lower} daf {daf}",
                ]
                if any(p in link_text_lower for p in daf_patterns) or \
                   re.search(rf'{masechta_lower}\s+{daf}\b', link_text_lower):
                    page_url = f"{ALLDAF_BASE_URL}{href}"
                    title = link_text
                    break

        if not page_url:
            raise ValueError(f"Could not find Jewish History video for {masechta} {daf}")

        # Fetch video page to get direct MP4 URL
        logger.info(f"Fetching video page: {page_url}")
        response = await client.get(page_url)
        response.raise_for_status()

        video_url = None
        mp4_match = re.search(
            r'https://(?:cdn\.jwplayer\.com|content\.jwplatform\.com)/videos/([a-zA-Z0-9]+)\.mp4',
            response.text
        )
        if mp4_match:
            video_url = f"https://cdn.jwplayer.com/videos/{mp4_match.group(1)}.mp4"

        return {
            'title': title,
            'page_url': page_url,
            'video_url': video_url,
            'masechta': masechta,
            'daf': daf
        }


async def send_daily_video():
    """Fetch and send today's video."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")

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
        logger.info(f"Sending video: {video_info['video_url']}")
        await bot.send_video(
            chat_id=TELEGRAM_CHAT_ID,
            video=video_info['video_url'],
            caption=caption,
            parse_mode='Markdown',
            supports_streaming=True
        )
    else:
        message = f"{caption}\n\n[Watch the video]({video_info['page_url']})"
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
            parse_mode='Markdown',
            disable_web_page_preview=False
        )

    logger.info("Message sent successfully!")


if __name__ == '__main__':
    asyncio.run(send_daily_video())
