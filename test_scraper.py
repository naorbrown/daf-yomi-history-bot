#!/usr/bin/env python3
"""
Test script to verify the alldaf.org scraping works correctly.
Run this to test without needing Telegram credentials.
"""

import asyncio
import re
import httpx
from bs4 import BeautifulSoup

SEFARIA_CALENDARS_URL = "https://www.sefaria.org/api/calendars"
ALLDAF_BASE_URL = "https://alldaf.org"

# Mapping from Sefaria masechta names to AllDaf names
MASECHTA_MAP = {
    'Berakhot': 'Berachos',
    'Shabbat': 'Shabbos',
    'Pesachim': 'Pesachim',
    'Shekalim': 'Shekalim',
    'Yoma': 'Yoma',
    'Sukkah': 'Succah',
    'Beitzah': 'Beitzah',
    'Rosh Hashanah': 'Rosh Hashanah',
    'Taanit': 'Taanis',
    'Megillah': 'Megilah',
    'Moed Katan': 'Moed Katan',
    'Chagigah': 'Chagiga',
    'Yevamot': 'Yevamos',
    'Ketubot': 'Kesuvos',
    'Nedarim': 'Nedarim',
    'Nazir': 'Nazir',
    'Sotah': 'Sotah',
    'Gittin': 'Gitin',
    'Kiddushin': 'Kidushin',
    'Bava Kamma': 'Bava Kama',
    'Bava Metzia': 'Bava Metzia',
    'Bava Batra': 'Bava Basra',
    'Sanhedrin': 'Sanhedrin',
    'Makkot': 'Makos',
    'Shevuot': 'Shevuos',
    'Avodah Zarah': 'Avodah Zarah',
    'Horayot': 'Horayos',
    'Zevachim': 'Zevachim',
    'Menachot': 'Menachos',
    'Chullin': 'Chulin',
    'Bekhorot': 'Bechoros',
    'Arakhin': 'Erchin',
    'Temurah': 'Temurah',
    'Keritot': 'Kerisus',
    'Meilah': 'Meilah',
    'Niddah': 'Nidah',
}


def convert_masechta_name(sefaria_name: str) -> str:
    """Convert Sefaria masechta name to AllDaf format."""
    return MASECHTA_MAP.get(sefaria_name, sefaria_name)


async def get_todays_daf_info() -> dict:
    """Fetch today's daf information from Sefaria's calendar API."""
    async with httpx.AsyncClient() as client:
        response = await client.get(SEFARIA_CALENDARS_URL)
        response.raise_for_status()
        data = response.json()

        for item in data.get('calendar_items', []):
            if item.get('title', {}).get('en') == 'Daf Yomi':
                ref = item.get('ref', '')
                match = re.match(r'(.+)\s+(\d+)', ref)
                if match:
                    sefaria_masechta = match.group(1)
                    daf = int(match.group(2))
                    alldaf_masechta = convert_masechta_name(sefaria_masechta)
                    return {
                        'masechta': alldaf_masechta,
                        'daf': daf,
                        'sefaria_name': sefaria_masechta
                    }

        raise ValueError("Could not find Daf Yomi in Sefaria calendar")


async def get_jewish_history_video(masechta: str, daf: int) -> dict:
    """Find the Jewish History in Daf Yomi video for a specific daf."""
    series_url = f"{ALLDAF_BASE_URL}/series/3940"
    print(f"Checking series page: {series_url}")

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        response = await client.get(series_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        masechta_lower = masechta.lower()

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
                    f"{masechta_lower}{daf}",
                ]
                if any(p in link_text_lower for p in daf_patterns) or \
                   re.search(rf'{masechta_lower}\s+{daf}\b', link_text_lower):
                    video_url = f"{ALLDAF_BASE_URL}{href}"
                    return {
                        'title': link_text,
                        'url': video_url,
                        'masechta': masechta,
                        'daf': daf
                    }

        # If not found on series page, try the daf page directly
        daf_page_url = f"{ALLDAF_BASE_URL}/?masechta={masechta}&daf={daf}"
        print(f"Trying daf page: {daf_page_url}")

        response = await client.get(daf_page_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        for link in soup.find_all('a', href=True):
            href = link['href']
            if not href.startswith('/p/'):
                continue

            parent = link.find_parent(['div', 'li', 'section'])
            if parent:
                parent_text = parent.get_text().lower()
                if 'jewish history' in parent_text or 'abramson' in parent_text or 'henry' in parent_text:
                    link_text = link.get_text().strip()
                    if link_text and masechta_lower in link_text.lower():
                        video_url = f"{ALLDAF_BASE_URL}{href}"
                        return {
                            'title': link_text,
                            'url': video_url,
                            'masechta': masechta,
                            'daf': daf
                        }

        raise ValueError(f"Could not find Jewish History video for {masechta} {daf}")


async def main():
    print("=" * 60)
    print("Testing Daf Yomi History Scraper")
    print("=" * 60)

    try:
        print("\n1. Getting today's daf info from Sefaria...")
        daf_info = await get_todays_daf_info()
        print(f"   Sefaria name: {daf_info['sefaria_name']}")
        print(f"   AllDaf name: {daf_info['masechta']}")
        print(f"   Daf: {daf_info['daf']}")

        print("\n2. Finding Jewish History video...")
        video_info = await get_jewish_history_video(daf_info['masechta'], daf_info['daf'])
        print(f"   Found video: {video_info['title']}")
        print(f"   URL: {video_info['url']}")

        print("\n" + "=" * 60)
        print("SUCCESS! Scraping works correctly.")
        print("=" * 60)

        print("\nSample Telegram message:")
        print("-" * 40)
        message = (
            f"*Today's Daf Yomi History*\n\n"
            f"*{video_info['masechta']} {video_info['daf']}*\n"
            f"{video_info['title']}\n\n"
            f"Watch: {video_info['url']}"
        )
        print(message)

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(main())
