"""
Comprehensive test suite for Daf Yomi History Bot.

Tests cover:
- Daf fetching from Hebcal API
- Video discovery from AllDaf.org
- Masechta name conversion
- Webhook handler logic
- Error handling
"""

import json
import os
import re
import sys
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.webhook import (
    MASECHTA_NAME_MAP,
    WELCOME_MESSAGE,
    HELP_MESSAGE,
    get_todays_daf,
    get_video_info,
    process_update,
    send_message,
)


class TestMasechtaNameMapping(unittest.TestCase):
    """Test masechta name conversion."""

    def test_known_mappings(self):
        """Test that known Hebcal names map correctly to AllDaf names."""
        test_cases = [
            ("Berakhot", "Berachos"),
            ("Shabbat", "Shabbos"),
            ("Menachot", "Menachos"),
            ("Bava Kamma", "Bava Kama"),
            ("Ketubot", "Kesuvos"),
        ]
        for hebcal_name, expected in test_cases:
            with self.subTest(hebcal_name=hebcal_name):
                self.assertEqual(
                    MASECHTA_NAME_MAP.get(hebcal_name, hebcal_name),
                    expected
                )

    def test_unknown_mapping_returns_original(self):
        """Test that unknown names are returned unchanged."""
        unknown_name = "SomeUnknownMasechta"
        self.assertEqual(
            MASECHTA_NAME_MAP.get(unknown_name, unknown_name),
            unknown_name
        )

    def test_all_mappings_exist(self):
        """Test that all expected masechtot have mappings."""
        expected_masechtot = [
            "Berakhot", "Shabbat", "Sukkah", "Taanit", "Megillah",
            "Chagigah", "Yevamot", "Ketubot", "Gittin", "Kiddushin",
            "Bava Kamma", "Bava Batra", "Makkot", "Shevuot", "Horayot",
            "Menachot", "Chullin", "Bekhorot", "Arakhin", "Keritot", "Niddah"
        ]
        for masechta in expected_masechtot:
            with self.subTest(masechta=masechta):
                self.assertIn(masechta, MASECHTA_NAME_MAP)


class TestMessages(unittest.TestCase):
    """Test bot messages."""

    def test_welcome_message_contains_commands(self):
        """Test welcome message lists all commands."""
        self.assertIn("/today", WELCOME_MESSAGE)
        self.assertIn("/help", WELCOME_MESSAGE)

    def test_welcome_message_contains_schedule(self):
        """Test welcome message mentions schedule."""
        self.assertIn("6:00 AM Israel time", WELCOME_MESSAGE)

    def test_help_message_contains_commands(self):
        """Test help message lists all commands."""
        self.assertIn("/today", HELP_MESSAGE)
        self.assertIn("/help", HELP_MESSAGE)

    def test_help_message_contains_repo(self):
        """Test help message contains repo link."""
        self.assertIn("github.com/naorbrown/daf-yomi-history-bot", HELP_MESSAGE)


class TestHebcalAPI(unittest.TestCase):
    """Test Hebcal API integration."""

    @patch("api.webhook.fetch_url")
    def test_get_todays_daf_success(self, mock_fetch):
        """Test successful daf fetching."""
        mock_response = {
            "items": [
                {
                    "category": "dafyomi",
                    "title": "Menachos 17"
                }
            ]
        }
        mock_fetch.return_value = json.dumps(mock_response)

        masechta, daf = get_todays_daf()

        self.assertEqual(masechta, "Menachos")
        self.assertEqual(daf, 17)

    @patch("api.webhook.fetch_url")
    def test_get_todays_daf_with_mapping(self, mock_fetch):
        """Test daf fetching with name mapping."""
        mock_response = {
            "items": [
                {
                    "category": "dafyomi",
                    "title": "Berakhot 10"
                }
            ]
        }
        mock_fetch.return_value = json.dumps(mock_response)

        masechta, daf = get_todays_daf()

        self.assertEqual(masechta, "Berachos")  # Mapped name
        self.assertEqual(daf, 10)

    @patch("api.webhook.fetch_url")
    def test_get_todays_daf_no_daf_found(self, mock_fetch):
        """Test error when no daf found."""
        mock_response = {"items": []}
        mock_fetch.return_value = json.dumps(mock_response)

        with self.assertRaises(ValueError) as context:
            get_todays_daf()

        self.assertIn("No Daf Yomi found", str(context.exception))


class TestVideoDiscovery(unittest.TestCase):
    """Test video discovery from AllDaf."""

    @patch("api.webhook.fetch_url")
    def test_get_video_info_success(self, mock_fetch):
        """Test successful video discovery."""
        # Mock series page
        series_html = '''
        <html>
        <a href="/p/12345">Menachos 17 - Some Title</a>
        </html>
        '''
        # Mock video page
        video_html = '''
        <html>
        <script>
        https://cdn.jwplayer.com/videos/abc123.mp4
        </script>
        </html>
        '''
        mock_fetch.side_effect = [series_html, video_html]

        video = get_video_info("Menachos", 17)

        self.assertEqual(video["masechta"], "Menachos")
        self.assertEqual(video["daf"], 17)
        self.assertEqual(video["video_url"], "https://cdn.jwplayer.com/videos/abc123.mp4")
        self.assertIn("Menachos 17", video["title"])

    @patch("api.webhook.fetch_url")
    def test_get_video_info_not_found(self, mock_fetch):
        """Test error when video not found."""
        mock_fetch.return_value = "<html><body>No videos here</body></html>"

        with self.assertRaises(ValueError) as context:
            get_video_info("Menachos", 999)

        self.assertIn("Video not found", str(context.exception))


class TestWebhookHandler(unittest.TestCase):
    """Test webhook message processing."""

    @patch("api.webhook.send_message")
    def test_start_command(self, mock_send):
        """Test /start command sends welcome message."""
        update = {
            "message": {
                "text": "/start",
                "chat": {"id": 12345}
            }
        }

        process_update(update)

        mock_send.assert_called_once()
        call_args = mock_send.call_args
        self.assertEqual(call_args[0][0], 12345)
        self.assertIn("Welcome", call_args[0][1])

    @patch("api.webhook.send_message")
    def test_help_command(self, mock_send):
        """Test /help command sends help message."""
        update = {
            "message": {
                "text": "/help",
                "chat": {"id": 12345}
            }
        }

        process_update(update)

        mock_send.assert_called_once()
        call_args = mock_send.call_args
        self.assertEqual(call_args[0][0], 12345)
        self.assertIn("Help", call_args[0][1])

    @patch("api.webhook.handle_today_command")
    def test_today_command(self, mock_today):
        """Test /today command triggers video fetch."""
        update = {
            "message": {
                "text": "/today",
                "chat": {"id": 12345}
            }
        }

        process_update(update)

        mock_today.assert_called_once_with(12345)

    def test_no_chat_id_does_nothing(self):
        """Test that updates without chat_id are ignored."""
        update = {
            "message": {
                "text": "/start"
            }
        }

        # Should not raise
        process_update(update)

    def test_empty_update_does_nothing(self):
        """Test that empty updates are ignored."""
        process_update({})


class TestRegexPatterns(unittest.TestCase):
    """Test regex patterns used in video discovery."""

    def test_mp4_url_pattern(self):
        """Test MP4 URL extraction pattern."""
        pattern = r"https://(?:cdn\.jwplayer\.com|content\.jwplatform\.com)/videos/([a-zA-Z0-9]+)\.mp4"

        test_cases = [
            ("https://cdn.jwplayer.com/videos/abc123.mp4", "abc123"),
            ("https://content.jwplatform.com/videos/XYZ789.mp4", "XYZ789"),
        ]

        for url, expected_id in test_cases:
            with self.subTest(url=url):
                match = re.search(pattern, url)
                self.assertIsNotNone(match)
                self.assertEqual(match.group(1), expected_id)

    def test_daf_title_pattern(self):
        """Test daf title parsing pattern."""
        pattern = r"(.+)\s+(\d+)"

        test_cases = [
            ("Menachos 17", ("Menachos", "17")),
            ("Bava Kamma 45", ("Bava Kamma", "45")),
            ("Berakhot 2", ("Berakhot", "2")),
        ]

        for title, expected in test_cases:
            with self.subTest(title=title):
                match = re.match(pattern, title)
                self.assertIsNotNone(match)
                self.assertEqual(match.groups(), expected)


class TestIntegration(unittest.TestCase):
    """Integration tests (require network, marked for optional skip)."""

    @unittest.skipIf(
        os.environ.get("SKIP_INTEGRATION_TESTS"),
        "Integration tests disabled"
    )
    def test_hebcal_api_returns_valid_daf(self):
        """Test real Hebcal API returns valid data."""
        masechta, daf = get_todays_daf()

        self.assertIsInstance(masechta, str)
        self.assertGreater(len(masechta), 0)
        self.assertIsInstance(daf, int)
        self.assertGreater(daf, 0)

    @unittest.skipIf(
        os.environ.get("SKIP_INTEGRATION_TESTS"),
        "Integration tests disabled"
    )
    def test_alldaf_series_page_accessible(self):
        """Test AllDaf series page is accessible."""
        from api.webhook import fetch_url, ALLDAF_SERIES_URL

        html = fetch_url(ALLDAF_SERIES_URL)

        self.assertIn("alldaf", html.lower())


if __name__ == "__main__":
    unittest.main()
