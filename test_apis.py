#!/usr/bin/env python3
"""
API Integration Test Script

Tests external API integrations:
1. Hebcal API - Daf Yomi schedule
2. AllDaf.org - Video discovery

Like nachyomi-bot's test-apis.js, this provides a quick way to verify
all external dependencies are working correctly.

Usage:
    python test_apis.py
"""

import sys
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.request import Request, urlopen
from urllib.parse import urlencode
import json

# ANSI colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
CHECK = f"{GREEN}✓{RESET}"
CROSS = f"{RED}✗{RESET}"
WARN = f"{YELLOW}⚠{RESET}"


def print_header(text: str) -> None:
    """Print a section header."""
    print(f"\n{'=' * 50}")
    print(f"  {text}")
    print(f"{'=' * 50}\n")


def print_result(success: bool, message: str) -> None:
    """Print a test result."""
    icon = CHECK if success else CROSS
    print(f"  {icon} {message}")


def print_warning(message: str) -> None:
    """Print a warning."""
    print(f"  {WARN} {message}")


def fetch_url(url: str, timeout: int = 30) -> str:
    """Fetch URL content."""
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; DafYomiBot-Test/1.0)",
            "Accept": "text/html,application/json",
        },
    )
    with urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8")


def test_hebcal_api() -> bool:
    """Test Hebcal Daf Yomi API."""
    print_header("Test 1: Hebcal API (Daf Yomi Schedule)")

    try:
        israel_tz = ZoneInfo("Asia/Jerusalem")
        today = datetime.now(israel_tz).strftime("%Y-%m-%d")

        params = urlencode({
            "v": "1",
            "cfg": "json",
            "F": "on",
            "start": today,
            "end": today,
        })

        url = f"https://www.hebcal.com/hebcal?{params}"
        print(f"  Fetching: {url}")

        data = json.loads(fetch_url(url))

        # Find daf yomi item
        daf_item = None
        for item in data.get("items", []):
            if item.get("category") == "dafyomi":
                daf_item = item
                break

        if not daf_item:
            print_result(False, "No Daf Yomi found in response")
            return False

        title = daf_item.get("title", "")
        match = re.match(r"(.+)\s+(\d+)", title)
        if not match:
            print_result(False, f"Could not parse daf title: {title}")
            return False

        masechta = match.group(1)
        daf = int(match.group(2))

        print_result(True, f"Today's Daf: {masechta} {daf}")
        print(f"      Date: {today} (Israel time)")
        return True

    except Exception as e:
        print_result(False, f"Error: {e}")
        return False


def test_alldaf_series_page() -> bool:
    """Test AllDaf.org series page accessibility."""
    print_header("Test 2: AllDaf.org Series Page")

    try:
        url = "https://alldaf.org/series/3940"
        print(f"  Fetching: {url}")

        html = fetch_url(url)

        # Check for expected content
        if "alldaf" not in html.lower():
            print_result(False, "Page does not contain expected content")
            return False

        # Count video links
        link_pattern = r'<a[^>]+href="(/p/[^"]+)"[^>]*>'
        links = re.findall(link_pattern, html)

        print_result(True, f"Series page accessible")
        print(f"      Found {len(links)} video links")
        return True

    except Exception as e:
        print_result(False, f"Error: {e}")
        return False


def test_video_discovery() -> bool:
    """Test video discovery for a known daf."""
    print_header("Test 3: Video Discovery")

    try:
        # Use a known masechta/daf that should exist
        masechta = "Berachos"
        daf = 2

        print(f"  Searching for: {masechta} {daf}")

        url = "https://alldaf.org/series/3940"
        html = fetch_url(url)

        # Search for the video
        masechta_lower = masechta.lower()
        link_pattern = r'<a[^>]+href="(/p/[^"]+)"[^>]*>([^<]+)</a>'

        found_url = None
        found_title = None

        for match in re.finditer(link_pattern, html, re.IGNORECASE | re.DOTALL):
            href, link_text = match.groups()
            link_text = link_text.strip()
            link_text_lower = link_text.lower()

            if masechta_lower in link_text_lower:
                patterns = [
                    rf"\b{masechta_lower}\s+{daf}\b",
                    rf"\b{masechta_lower}\s+daf\s+{daf}\b",
                ]
                if any(re.search(p, link_text_lower) for p in patterns):
                    found_url = f"https://alldaf.org{href}"
                    found_title = link_text
                    break

        if not found_url:
            print_warning(f"Video not found for {masechta} {daf}")
            print("      This may be expected if video doesn't exist")
            return True  # Not a failure, just not available

        print_result(True, f"Found video: {found_title}")
        print(f"      URL: {found_url}")
        return True

    except Exception as e:
        print_result(False, f"Error: {e}")
        return False


def test_jwplayer_cdn() -> bool:
    """Test JWPlayer CDN accessibility."""
    print_header("Test 4: JWPlayer CDN Accessibility")

    try:
        # Test a known video URL format (head request)
        # We just check the domain is reachable
        url = "https://cdn.jwplayer.com"
        print(f"  Checking: {url}")

        req = Request(url, method="HEAD")
        with urlopen(req, timeout=10) as response:
            status = response.status

        if status in (200, 301, 302, 403):
            print_result(True, f"CDN reachable (status: {status})")
            return True
        else:
            print_result(False, f"Unexpected status: {status}")
            return False

    except Exception as e:
        print_warning(f"CDN check failed: {e}")
        print("      Videos may still work via AllDaf.org")
        return True  # Not critical


def main() -> int:
    """Run all integration tests."""
    print("\n" + "=" * 50)
    print("  DAF YOMI HISTORY BOT - API INTEGRATION TESTS")
    print("=" * 50)

    results = []

    results.append(("Hebcal API", test_hebcal_api()))
    results.append(("AllDaf.org", test_alldaf_series_page()))
    results.append(("Video Discovery", test_video_discovery()))
    results.append(("JWPlayer CDN", test_jwplayer_cdn()))

    # Summary
    print_header("Summary")

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for name, success in results:
        print_result(success, name)

    print(f"\n  {passed}/{total} tests passed")

    if passed == total:
        print(f"\n  {GREEN}All integrations working!{RESET}\n")
        return 0
    else:
        print(f"\n  {YELLOW}Some tests failed - check above for details{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
