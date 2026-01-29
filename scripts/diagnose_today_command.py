#!/usr/bin/env python3
"""
Diagnostic script for the /today command.

This script tests each component of the /today command flow individually
to identify where failures occur. Run with:

    python scripts/diagnose_today_command.py

Or with a specific test:

    python scripts/diagnose_today_command.py --test hebcal
    python scripts/diagnose_today_command.py --test alldaf
    python scripts/diagnose_today_command.py --test telegram
    python scripts/diagnose_today_command.py --test full
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

# Check dependencies
try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: pip install httpx")
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: beautifulsoup4 not installed. Run: pip install beautifulsoup4")
    sys.exit(1)


# Constants (same as poll_commands.py)
ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")
ALLDAF_BASE_URL = "https://alldaf.org"
ALLDAF_SERIES_URL = f"{ALLDAF_BASE_URL}/series/3940"
HEBCAL_API_URL = "https://www.hebcal.com/hebcal"
REQUEST_TIMEOUT = 30.0
TELEGRAM_API_BASE = "https://api.telegram.org/bot"

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
    masechta: str
    daf: int


@dataclass
class VideoInfo:
    title: str
    page_url: str
    video_url: Optional[str]
    masechta: str
    daf: int


def print_header(title: str) -> None:
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def print_success(msg: str) -> None:
    print(f"✅ {msg}")


def print_error(msg: str) -> None:
    print(f"❌ {msg}")


def print_warning(msg: str) -> None:
    print(f"⚠️  {msg}")


def print_info(msg: str) -> None:
    print(f"ℹ️  {msg}")


def convert_masechta_name(hebcal_name: str) -> str:
    return MASECHTA_NAME_MAP.get(hebcal_name, hebcal_name)


# =============================================================================
# TEST 1: HEBCAL API
# =============================================================================

async def test_hebcal_api() -> Optional[DafInfo]:
    """Test the Hebcal API to get today's daf."""
    print_header("TEST 1: HEBCAL API")

    israel_now = datetime.now(ISRAEL_TZ)
    today_str = israel_now.strftime("%Y-%m-%d")
    print_info(f"Testing for date: {today_str} (Israel time: {israel_now.strftime('%H:%M')})")

    params = {
        "v": "1",
        "cfg": "json",
        "F": "on",
        "start": today_str,
        "end": today_str,
    }

    url = f"{HEBCAL_API_URL}?{httpx.QueryParams(params)}"
    print_info(f"Request URL: {url}")

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(HEBCAL_API_URL, params=params)

            print_info(f"Response status: {response.status_code}")

            if response.status_code != 200:
                print_error(f"HTTP error: {response.status_code}")
                print(f"Response body: {response.text[:500]}")
                return None

            data = response.json()
            print_info(f"Response contains {len(data.get('items', []))} items")

            # Print all items for debugging
            for i, item in enumerate(data.get("items", [])):
                category = item.get("category", "unknown")
                title = item.get("title", "unknown")
                print(f"  Item {i + 1}: [{category}] {title}")

            # Find daf yomi
            for item in data.get("items", []):
                if item.get("category") == "dafyomi":
                    title = item.get("title", "")
                    print_info(f"Found dafyomi item: '{title}'")

                    match = re.match(r"(.+)\s+(\d+)", title)
                    if match:
                        hebcal_masechta = match.group(1)
                        daf = int(match.group(2))
                        alldaf_masechta = convert_masechta_name(hebcal_masechta)

                        print_success(f"Parsed daf: {alldaf_masechta} {daf}")
                        print_info(f"Hebcal name: '{hebcal_masechta}' -> AllDaf name: '{alldaf_masechta}'")

                        return DafInfo(masechta=alldaf_masechta, daf=daf)
                    else:
                        print_error(f"Could not parse daf from title: '{title}'")
                        return None

            print_error("No dafyomi item found in response")
            return None

    except httpx.TimeoutException:
        print_error("Request timed out")
        return None
    except httpx.RequestError as e:
        print_error(f"Request error: {type(e).__name__}: {e}")
        return None
    except json.JSONDecodeError as e:
        print_error(f"JSON decode error: {e}")
        return None
    except Exception as e:
        print_error(f"Unexpected error: {type(e).__name__}: {e}")
        return None


# =============================================================================
# TEST 2: ALLDAF SCRAPING
# =============================================================================

async def test_alldaf_scraping(daf: DafInfo) -> Optional[VideoInfo]:
    """Test scraping AllDaf.org for the video."""
    print_header("TEST 2: ALLDAF.ORG SCRAPING")

    print_info(f"Looking for video: {daf.masechta} {daf.daf}")
    print_info(f"Series URL: {ALLDAF_SERIES_URL}")

    masechta_lower = daf.masechta.lower()

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=REQUEST_TIMEOUT) as client:
            # Step 1: Fetch series page
            print_info("Fetching series page...")
            response = await client.get(ALLDAF_SERIES_URL)

            print_info(f"Response status: {response.status_code}")

            if response.status_code != 200:
                print_error(f"HTTP error: {response.status_code}")
                return None

            print_info(f"Response size: {len(response.text)} bytes")

            # Step 2: Parse HTML
            soup = BeautifulSoup(response.text, "html.parser")
            all_links = soup.find_all("a", href=True)
            print_info(f"Found {len(all_links)} total links on page")

            # Step 3: Filter video links
            video_links = [link for link in all_links if link["href"].startswith("/p/")]
            print_info(f"Found {len(video_links)} video links (starting with /p/)")

            if len(video_links) == 0:
                print_error("No video links found! Page structure may have changed.")
                print_info("First 1000 chars of page:")
                print(response.text[:1000])
                return None

            # Step 4: Show some sample links
            print_info("Sample video links:")
            for link in video_links[:5]:
                print(f"  - {link.get_text().strip()[:60]}")

            # Step 5: Find matching video
            print_info(f"\nSearching for '{masechta_lower} {daf.daf}'...")

            page_url = None
            title = None
            matching_candidates = []

            patterns = [
                rf"{re.escape(masechta_lower)}\s+{daf.daf}\b",
                rf"{re.escape(masechta_lower)}\s+daf\s+{daf.daf}\b",
            ]

            for link in video_links:
                link_text = link.get_text().strip()
                link_text_lower = link_text.lower()

                # Check if masechta is in the text
                if masechta_lower in link_text_lower:
                    matching_candidates.append(link_text)

                    # Check for exact daf match
                    if any(re.search(p, link_text_lower) for p in patterns):
                        page_url = f"{ALLDAF_BASE_URL}{link['href']}"
                        title = link_text
                        break

            print_info(f"Found {len(matching_candidates)} links containing '{masechta_lower}':")
            for candidate in matching_candidates[:10]:
                print(f"  - {candidate}")

            if not page_url:
                print_error(f"No exact match found for {daf.masechta} {daf.daf}")
                print_warning("This could mean:")
                print("  1. The video doesn't exist yet for this daf")
                print("  2. The video title format is different than expected")
                print("  3. The page structure has changed")
                return None

            print_success(f"Found video: {title}")
            print_info(f"Page URL: {page_url}")

            # Step 6: Fetch video page for MP4 URL
            print_info("\nFetching video page for MP4 URL...")
            response = await client.get(page_url)

            if response.status_code != 200:
                print_error(f"HTTP error fetching video page: {response.status_code}")
                return VideoInfo(
                    title=title,
                    page_url=page_url,
                    video_url=None,
                    masechta=daf.masechta,
                    daf=daf.daf,
                )

            # Step 7: Extract MP4 URL
            mp4_pattern = (
                r"https://(?:cdn\.jwplayer\.com|content\.jwplatform\.com)"
                r"/videos/([a-zA-Z0-9]+)\.mp4"
            )
            mp4_match = re.search(mp4_pattern, response.text)

            video_url = None
            if mp4_match:
                video_url = f"https://cdn.jwplayer.com/videos/{mp4_match.group(1)}.mp4"
                print_success(f"Found MP4 URL: {video_url}")
            else:
                print_warning("No MP4 URL found in video page")
                print_info("Will send text message instead of video")

            return VideoInfo(
                title=title,
                page_url=page_url,
                video_url=video_url,
                masechta=daf.masechta,
                daf=daf.daf,
            )

    except httpx.TimeoutException:
        print_error("Request timed out")
        return None
    except httpx.RequestError as e:
        print_error(f"Request error: {type(e).__name__}: {e}")
        return None
    except Exception as e:
        print_error(f"Unexpected error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return None


# =============================================================================
# TEST 3: TELEGRAM API
# =============================================================================

async def test_telegram_api() -> bool:
    """Test the Telegram API connection."""
    print_header("TEST 3: TELEGRAM API")

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print_error("TELEGRAM_BOT_TOKEN environment variable not set")
        print_info("Set it with: export TELEGRAM_BOT_TOKEN=your_token")
        return False

    print_info(f"Token length: {len(token)} characters")
    print_info(f"Token prefix: {token[:10]}...")

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            # Test getMe
            print_info("Calling getMe...")
            response = await client.get(f"{TELEGRAM_API_BASE}{token}/getMe")
            data = response.json()

            if data.get("ok"):
                bot = data.get("result", {})
                print_success(f"Bot connected: @{bot.get('username', 'unknown')}")
                print_info(f"Bot ID: {bot.get('id')}")
                print_info(f"Bot name: {bot.get('first_name')}")
            else:
                print_error(f"getMe failed: {data}")
                return False

            # Test getWebhookInfo
            print_info("\nChecking webhook status...")
            response = await client.get(f"{TELEGRAM_API_BASE}{token}/getWebhookInfo")
            data = response.json()

            if data.get("ok"):
                webhook = data.get("result", {})
                webhook_url = webhook.get("url", "")
                if webhook_url:
                    print_warning(f"Webhook is SET: {webhook_url}")
                    print_warning("This may interfere with polling!")
                else:
                    print_success("No webhook set (polling should work)")

                pending = webhook.get("pending_update_count", 0)
                print_info(f"Pending updates: {pending}")
            else:
                print_error(f"getWebhookInfo failed: {data}")

            # Test getUpdates
            print_info("\nTesting getUpdates...")
            response = await client.post(
                f"{TELEGRAM_API_BASE}{token}/getUpdates",
                data={"timeout": 0, "limit": 1},
            )
            data = response.json()

            if data.get("ok"):
                updates = data.get("result", [])
                print_success(f"getUpdates works! Got {len(updates)} updates")
            else:
                error_code = data.get("error_code")
                description = data.get("description", "")
                print_error(f"getUpdates failed: {error_code} - {description}")

                if error_code == 409:
                    print_warning("Webhook conflict! Run deleteWebhook first.")
                return False

            return True

    except httpx.TimeoutException:
        print_error("Request timed out")
        return False
    except httpx.RequestError as e:
        print_error(f"Request error: {type(e).__name__}: {e}")
        return False
    except Exception as e:
        print_error(f"Unexpected error: {type(e).__name__}: {e}")
        return False


# =============================================================================
# FULL FLOW TEST
# =============================================================================

async def test_full_flow() -> bool:
    """Test the complete /today command flow."""
    print_header("FULL FLOW TEST")

    # Step 1: Get today's daf
    print("\n--- Step 1: Get today's daf from Hebcal ---")
    daf = await test_hebcal_api()
    if not daf:
        print_error("FLOW FAILED at step 1: Could not get today's daf")
        return False

    # Step 2: Find video on AllDaf
    print("\n--- Step 2: Find video on AllDaf.org ---")
    video = await test_alldaf_scraping(daf)
    if not video:
        print_error("FLOW FAILED at step 2: Could not find video")
        return False

    # Step 3: Test Telegram API (optional)
    print("\n--- Step 3: Test Telegram API ---")
    telegram_ok = await test_telegram_api()
    if not telegram_ok:
        print_warning("Telegram API test failed, but this may be expected without token")

    # Summary
    print_header("FLOW SUMMARY")
    print_success(f"Today's daf: {daf.masechta} {daf.daf}")
    print_success(f"Video title: {video.title}")
    print_success(f"Video page: {video.page_url}")
    if video.video_url:
        print_success(f"Video URL: {video.video_url}")
    else:
        print_warning("No direct video URL (will send link instead)")

    print("\n" + "=" * 60)
    print(" THE /today COMMAND SHOULD WORK!")
    print("=" * 60)

    return True


# =============================================================================
# MAIN
# =============================================================================

async def main():
    parser = argparse.ArgumentParser(description="Diagnose /today command issues")
    parser.add_argument(
        "--test",
        choices=["hebcal", "alldaf", "telegram", "full"],
        default="full",
        help="Which test to run (default: full)",
    )
    parser.add_argument(
        "--masechta",
        help="Override masechta name for AllDaf test",
    )
    parser.add_argument(
        "--daf",
        type=int,
        help="Override daf number for AllDaf test",
    )
    args = parser.parse_args()

    print("=" * 60)
    print(" DAF YOMI BOT - /today COMMAND DIAGNOSTIC")
    print("=" * 60)

    if args.test == "hebcal":
        await test_hebcal_api()
    elif args.test == "alldaf":
        if args.masechta and args.daf:
            daf = DafInfo(masechta=args.masechta, daf=args.daf)
        else:
            daf = await test_hebcal_api()
            if not daf:
                print_error("Cannot test AllDaf without daf info")
                return 1
        await test_alldaf_scraping(daf)
    elif args.test == "telegram":
        await test_telegram_api()
    else:
        success = await test_full_flow()
        return 0 if success else 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
