#!/usr/bin/env python3
"""
Comprehensive integration tests for the /today command.

These tests verify the complete flow from command parsing to video delivery,
with mocked external services (Hebcal API, AllDaf.org, Telegram API).
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import sys

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from poll_commands import (
    TelegramAPI,
    StateManager,
    RateLimiter,
    DafInfo,
    VideoInfo,
    parse_command,
    convert_masechta_name,
    get_todays_daf,
    get_jewish_history_video,
    handle_command,
    process_updates,
    main,
    _match_video_title,
    WELCOME_MESSAGE,
    HELP_MESSAGE,
    ERROR_MESSAGE,
)


# =============================================================================
# REALISTIC MOCK DATA
# =============================================================================

# Sample Hebcal API response for a specific date
HEBCAL_RESPONSE_SANHEDRIN_2 = {
    "title": "Hebcal Diaspora January 2026",
    "date": "2026-01-29",
    "items": [
        {
            "title": "Sanhedrin 2",
            "date": "2026-01-29",
            "category": "dafyomi",
            "hebrew": "סנהדרין ב׳",
        }
    ],
}

HEBCAL_RESPONSE_BERACHOS_15 = {
    "title": "Hebcal Diaspora",
    "date": "2024-01-15",
    "items": [
        {
            "title": "Berakhot 15",
            "date": "2024-01-15",
            "category": "dafyomi",
            "hebrew": "ברכות ט״ו",
        }
    ],
}

HEBCAL_RESPONSE_NO_DAF = {
    "title": "Hebcal Diaspora",
    "date": "2024-01-15",
    "items": [],
}

# Sample AllDaf series page HTML (simplified but realistic)
ALLDAF_SERIES_PAGE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Jewish History Series - AllDaf.org</title></head>
<body>
<div class="series-list">
    <a href="/p/12345">Berachos 2 - Introduction to Jewish History</a>
    <a href="/p/12346">Berachos 3 - Early Period</a>
    <a href="/p/12347">Berachos 15 - Medieval Era</a>
    <a href="/p/12348">Shabbos 2 - Sabbath Origins</a>
    <a href="/p/12349">Sanhedrin 2 - Courts and Justice</a>
    <a href="/p/12350">Sanhedrin 3 - Legal Systems</a>
</div>
</body>
</html>
"""

# Sample AllDaf video page HTML with JWPlayer URL
ALLDAF_VIDEO_PAGE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Sanhedrin 2 - Courts and Justice</title></head>
<body>
<div class="video-player">
    <script>
        jwplayer("player").setup({
            "file": "https://cdn.jwplayer.com/videos/abc123XYZ.mp4",
            "title": "Sanhedrin 2 - Courts and Justice"
        });
    </script>
</div>
</body>
</html>
"""

ALLDAF_VIDEO_PAGE_NO_MP4 = """
<!DOCTYPE html>
<html>
<head><title>Sanhedrin 2 - Courts and Justice</title></head>
<body>
<div class="video-player">
    <iframe src="https://example.com/embed/video"></iframe>
</div>
</body>
</html>
"""


# =============================================================================
# TEST: COMMAND PARSING
# =============================================================================

class TestCommandParsing:
    """Tests for command parsing logic."""

    def test_parse_today_command(self):
        assert parse_command("/today") == "today"

    def test_parse_today_with_bot_mention(self):
        assert parse_command("/today@DafHistoryBot") == "today"

    def test_parse_today_uppercase(self):
        assert parse_command("/TODAY") == "today"

    def test_parse_today_mixed_case(self):
        assert parse_command("/TodAy") == "today"

    def test_parse_today_with_whitespace(self):
        assert parse_command("  /today  ") == "today"

    def test_parse_start_command(self):
        assert parse_command("/start") == "start"

    def test_parse_help_command(self):
        assert parse_command("/help") == "help"

    def test_parse_non_command(self):
        assert parse_command("hello") is None

    def test_parse_empty(self):
        assert parse_command("") is None

    def test_parse_none(self):
        assert parse_command(None) is None


# =============================================================================
# TEST: MASECHTA NAME CONVERSION
# =============================================================================

class TestMasechtaNameConversion:
    """Tests for Hebcal -> AllDaf name conversion."""

    def test_convert_berakhot(self):
        assert convert_masechta_name("Berakhot") == "Berachos"

    def test_convert_shabbat(self):
        assert convert_masechta_name("Shabbat") == "Shabbos"

    def test_convert_sanhedrin_unchanged(self):
        # Sanhedrin should not be mapped (same in both)
        assert convert_masechta_name("Sanhedrin") == "Sanhedrin"

    def test_convert_unknown_unchanged(self):
        assert convert_masechta_name("SomethingNew") == "SomethingNew"


# =============================================================================
# TEST: HEBCAL API - get_todays_daf()
# =============================================================================

class TestHebcalAPI:
    """Tests for Hebcal API integration."""

    @pytest.mark.asyncio
    async def test_get_todays_daf_success(self):
        """Test successful daf retrieval from Hebcal."""
        mock_response = MagicMock()
        mock_response.json.return_value = HEBCAL_RESPONSE_SANHEDRIN_2
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            daf = await get_todays_daf()

            assert daf.masechta == "Sanhedrin"
            assert daf.daf == 2

    @pytest.mark.asyncio
    async def test_get_todays_daf_with_name_conversion(self):
        """Test that Berakhot is converted to Berachos."""
        mock_response = MagicMock()
        mock_response.json.return_value = HEBCAL_RESPONSE_BERACHOS_15
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            daf = await get_todays_daf()

            assert daf.masechta == "Berachos"
            assert daf.daf == 15

    @pytest.mark.asyncio
    async def test_get_todays_daf_no_daf_found(self):
        """Test error when no daf is in the response."""
        mock_response = MagicMock()
        mock_response.json.return_value = HEBCAL_RESPONSE_NO_DAF
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(ValueError, match="No Daf Yomi found"):
                await get_todays_daf()


# =============================================================================
# TEST: ALLDAF SCRAPING - get_jewish_history_video()
# =============================================================================

class TestAllDafScraping:
    """Tests for AllDaf.org video scraping."""

    @pytest.mark.asyncio
    async def test_find_video_success(self):
        """Test successful video finding with MP4 URL."""
        series_response = MagicMock()
        series_response.text = ALLDAF_SERIES_PAGE_HTML
        series_response.raise_for_status = MagicMock()

        video_response = MagicMock()
        video_response.text = ALLDAF_VIDEO_PAGE_HTML
        video_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = [series_response, video_response]
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            daf = DafInfo(masechta="Sanhedrin", daf=2)
            video = await get_jewish_history_video(daf)

            assert video.masechta == "Sanhedrin"
            assert video.daf == 2
            assert video.title == "Sanhedrin 2 - Courts and Justice"
            assert video.page_url == "https://alldaf.org/p/12349"
            assert video.video_url == "https://cdn.jwplayer.com/videos/abc123XYZ.mp4"

    @pytest.mark.asyncio
    async def test_find_video_no_mp4_url(self):
        """Test video finding when MP4 URL cannot be extracted."""
        series_response = MagicMock()
        series_response.text = ALLDAF_SERIES_PAGE_HTML
        series_response.raise_for_status = MagicMock()

        video_response = MagicMock()
        video_response.text = ALLDAF_VIDEO_PAGE_NO_MP4
        video_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = [series_response, video_response]
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            daf = DafInfo(masechta="Sanhedrin", daf=2)
            video = await get_jewish_history_video(daf)

            assert video.page_url == "https://alldaf.org/p/12349"
            assert video.video_url is None  # No MP4 found

    @pytest.mark.asyncio
    async def test_find_video_not_found(self):
        """Test error when video for specific daf is not found."""
        series_response = MagicMock()
        series_response.text = ALLDAF_SERIES_PAGE_HTML
        series_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = series_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            # Looking for a daf that doesn't exist in the mock HTML
            daf = DafInfo(masechta="Sanhedrin", daf=99)

            with pytest.raises(ValueError, match="Video not found"):
                await get_jewish_history_video(daf)

    @pytest.mark.asyncio
    async def test_find_video_berachos_conversion(self):
        """Test finding video with converted masechta name (Berachos)."""
        series_response = MagicMock()
        series_response.text = ALLDAF_SERIES_PAGE_HTML
        series_response.raise_for_status = MagicMock()

        video_response = MagicMock()
        video_response.text = ALLDAF_VIDEO_PAGE_HTML
        video_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = [series_response, video_response]
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            daf = DafInfo(masechta="Berachos", daf=15)
            video = await get_jewish_history_video(daf)

            assert video.title == "Berachos 15 - Medieval Era"
            assert video.page_url == "https://alldaf.org/p/12347"


# =============================================================================
# TEST: HANDLE_COMMAND - /today
# =============================================================================

class TestHandleTodayCommand:
    """Tests for the /today command handler."""

    @pytest.mark.asyncio
    async def test_today_command_sends_video(self):
        """Test /today sends video when MP4 URL is available."""
        api = AsyncMock(spec=TelegramAPI)
        api.send_video.return_value = {"ok": True}

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            rate_file = Path(tmpdir) / "rate_limits.json"

            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.STATE_FILE", state_file):
                    with patch("poll_commands.RATE_LIMIT_FILE", rate_file):
                        state = StateManager()
                        rate_limiter = RateLimiter(state)

                        # Mock the daf and video fetching
                        with patch("poll_commands.get_todays_daf") as mock_daf:
                            with patch("poll_commands.get_jewish_history_video") as mock_video:
                                mock_daf.return_value = DafInfo(masechta="Sanhedrin", daf=2)
                                mock_video.return_value = VideoInfo(
                                    title="Sanhedrin 2 - Courts and Justice",
                                    page_url="https://alldaf.org/p/12349",
                                    video_url="https://cdn.jwplayer.com/videos/abc123XYZ.mp4",
                                    masechta="Sanhedrin",
                                    daf=2,
                                )

                                await handle_command(api, 123, "today", rate_limiter, 456)

                                # Verify send_video was called
                                api.send_video.assert_called_once()
                                call_args = api.send_video.call_args
                                assert call_args[0][0] == 123  # chat_id
                                assert "abc123XYZ.mp4" in call_args[0][1]  # video_url
                                assert "Sanhedrin 2" in call_args[0][2]  # caption

    @pytest.mark.asyncio
    async def test_today_command_sends_message_when_no_video_url(self):
        """Test /today sends text message when no MP4 URL is available."""
        api = AsyncMock(spec=TelegramAPI)
        api.send_message.return_value = {"ok": True}

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            rate_file = Path(tmpdir) / "rate_limits.json"

            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.STATE_FILE", state_file):
                    with patch("poll_commands.RATE_LIMIT_FILE", rate_file):
                        state = StateManager()
                        rate_limiter = RateLimiter(state)

                        with patch("poll_commands.get_todays_daf") as mock_daf:
                            with patch("poll_commands.get_jewish_history_video") as mock_video:
                                mock_daf.return_value = DafInfo(masechta="Sanhedrin", daf=2)
                                mock_video.return_value = VideoInfo(
                                    title="Sanhedrin 2 - Courts and Justice",
                                    page_url="https://alldaf.org/p/12349",
                                    video_url=None,  # No MP4 URL
                                    masechta="Sanhedrin",
                                    daf=2,
                                )

                                await handle_command(api, 123, "today", rate_limiter, 456)

                                # Verify send_message was called (not send_video)
                                api.send_message.assert_called_once()
                                api.send_video.assert_not_called()

    @pytest.mark.asyncio
    async def test_today_command_sends_error_on_failure(self):
        """Test /today sends error message when fetching fails."""
        api = AsyncMock(spec=TelegramAPI)
        api.send_message.return_value = {"ok": True}

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            rate_file = Path(tmpdir) / "rate_limits.json"

            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.STATE_FILE", state_file):
                    with patch("poll_commands.RATE_LIMIT_FILE", rate_file):
                        state = StateManager()
                        rate_limiter = RateLimiter(state)

                        with patch("poll_commands.get_todays_daf") as mock_daf:
                            mock_daf.side_effect = ValueError("API Error")

                            await handle_command(api, 123, "today", rate_limiter, 456)

                            # Verify error message was sent
                            api.send_message.assert_called_once()
                            call_args = api.send_message.call_args
                            assert call_args[0][0] == 123  # chat_id
                            # Check for either old or new error message format
                            msg = call_args[0][1].lower()
                            assert "couldn't" in msg or "sorry" in msg


# =============================================================================
# TEST: FULL FLOW - process_updates with /today
# =============================================================================

class TestFullTodayFlow:
    """End-to-end tests for the complete /today command flow."""

    @pytest.mark.asyncio
    async def test_full_today_flow_with_video(self):
        """Test complete flow: receive update -> process /today -> send video."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            rate_file = Path(tmpdir) / "rate_limits.json"

            # Pre-existing state
            state_file.write_text(json.dumps({"last_update_id": 100}))

            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.STATE_FILE", state_file):
                    with patch("poll_commands.RATE_LIMIT_FILE", rate_file):
                        state = StateManager()

                        # Mock API
                        api = AsyncMock(spec=TelegramAPI)
                        api.get_updates.return_value = [
                            {
                                "update_id": 101,
                                "message": {
                                    "text": "/today",
                                    "chat": {"id": 123},
                                    "from": {"id": 456},
                                },
                            }
                        ]
                        api.send_video.return_value = {"ok": True}

                        with patch("poll_commands.get_todays_daf") as mock_daf:
                            with patch("poll_commands.get_jewish_history_video") as mock_video:
                                mock_daf.return_value = DafInfo(masechta="Sanhedrin", daf=2)
                                mock_video.return_value = VideoInfo(
                                    title="Sanhedrin 2 - Courts",
                                    page_url="https://alldaf.org/p/12349",
                                    video_url="https://cdn.jwplayer.com/videos/abc.mp4",
                                    masechta="Sanhedrin",
                                    daf=2,
                                )

                                processed = await process_updates(api, state)

                                assert processed == 1
                                api.get_updates.assert_called_once_with(101)
                                api.send_video.assert_called_once()
                                mock_daf.assert_called_once()
                                mock_video.assert_called_once()

    @pytest.mark.asyncio
    async def test_full_today_flow_rate_limited(self):
        """Test /today is rate limited after too many requests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            rate_file = Path(tmpdir) / "rate_limits.json"

            # Pre-load rate limits (user already made 5 requests)
            import time
            now = time.time()
            rate_file.write_text(json.dumps({"456": [now - 10, now - 8, now - 6, now - 4, now - 2]}))
            state_file.write_text(json.dumps({"last_update_id": 100}))

            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.STATE_FILE", state_file):
                    with patch("poll_commands.RATE_LIMIT_FILE", rate_file):
                        state = StateManager()

                        api = AsyncMock(spec=TelegramAPI)
                        api.get_updates.return_value = [
                            {
                                "update_id": 101,
                                "message": {
                                    "text": "/today",
                                    "chat": {"id": 123},
                                    "from": {"id": 456},
                                },
                            }
                        ]
                        api.send_message.return_value = {"ok": True}

                        with patch("poll_commands.get_todays_daf") as mock_daf:
                            processed = await process_updates(api, state)

                            assert processed == 1
                            # Should send rate limit message, not fetch video
                            api.send_message.assert_called_once()
                            assert "too many" in api.send_message.call_args[0][1].lower()
                            mock_daf.assert_not_called()


# =============================================================================
# TEST: main() FUNCTION
# =============================================================================

class TestMainFunction:
    """Tests for the main() entry point."""

    @pytest.mark.asyncio
    async def test_main_with_today_command(self):
        """Test main() successfully processes a /today command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            rate_file = Path(tmpdir) / "rate_limits.json"

            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.STATE_FILE", state_file):
                    with patch("poll_commands.RATE_LIMIT_FILE", rate_file):
                        with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "test_token"}):
                            with patch("httpx.AsyncClient") as mock_client:
                                mock_instance = AsyncMock()
                                mock_instance.__aenter__.return_value = mock_instance
                                mock_instance.__aexit__.return_value = None
                                mock_client.return_value = mock_instance

                                # Responses for: deleteWebhook, getUpdates, sendVideo
                                delete_webhook_response = MagicMock(
                                    json=lambda: {"ok": True},
                                    raise_for_status=MagicMock(),
                                )
                                get_updates_response = MagicMock(
                                    json=lambda: {
                                        "ok": True,
                                        "result": [
                                            {
                                                "update_id": 100,
                                                "message": {
                                                    "text": "/today",
                                                    "chat": {"id": 123},
                                                    "from": {"id": 456},
                                                },
                                            }
                                        ],
                                    },
                                    raise_for_status=MagicMock(),
                                )
                                send_video_response = MagicMock(
                                    json=lambda: {"ok": True},
                                    raise_for_status=MagicMock(),
                                )

                                mock_instance.post.side_effect = [
                                    delete_webhook_response,
                                    get_updates_response,
                                    send_video_response,
                                ]

                                # Mock external APIs
                                with patch("poll_commands.get_todays_daf") as mock_daf:
                                    with patch("poll_commands.get_jewish_history_video") as mock_video:
                                        mock_daf.return_value = DafInfo(masechta="Sanhedrin", daf=2)
                                        mock_video.return_value = VideoInfo(
                                            title="Sanhedrin 2",
                                            page_url="https://alldaf.org/p/123",
                                            video_url="https://cdn.jwplayer.com/videos/x.mp4",
                                            masechta="Sanhedrin",
                                            daf=2,
                                        )

                                        result = await main()

                                        assert result == 0
                                        mock_daf.assert_called_once()
                                        mock_video.assert_called_once()


# =============================================================================
# TEST: VIDEO MATCHING PATTERNS
# =============================================================================

class TestVideoTitleMatching:
    """Tests for the _match_video_title function directly."""

    def test_simple_format(self):
        """Test 'Masechta N' format."""
        assert _match_video_title("Sanhedrin 2", "Sanhedrin", 2) is True

    def test_with_daf_keyword(self):
        """Test 'Masechta Daf N' format."""
        assert _match_video_title("Sanhedrin Daf 2", "Sanhedrin", 2) is True

    def test_with_description(self):
        """Test 'Masechta N - Description' format."""
        assert _match_video_title("Sanhedrin 2 - Courts and Justice", "Sanhedrin", 2) is True

    def test_case_insensitive(self):
        """Test case-insensitive matching."""
        assert _match_video_title("SANHEDRIN 2", "Sanhedrin", 2) is True
        assert _match_video_title("sanhedrin 2", "Sanhedrin", 2) is True

    def test_no_match_wrong_daf(self):
        """Test no match for wrong daf number."""
        assert _match_video_title("Sanhedrin 3", "Sanhedrin", 2) is False

    def test_no_match_partial_number(self):
        """Test no match when daf is part of larger number."""
        assert _match_video_title("Sanhedrin 22", "Sanhedrin", 2) is False
        assert _match_video_title("Sanhedrin 12", "Sanhedrin", 2) is False
        assert _match_video_title("Sanhedrin 20", "Sanhedrin", 2) is False

    def test_with_colon_separator(self):
        """Test 'Masechta: N' format."""
        assert _match_video_title("Sanhedrin: 2", "Sanhedrin", 2) is True

    def test_with_dash_separator(self):
        """Test 'Masechta - N' format."""
        assert _match_video_title("Sanhedrin - 2", "Sanhedrin", 2) is True

    def test_daf_at_end(self):
        """Test when daf number is at end of string."""
        assert _match_video_title("Jewish History Sanhedrin 2", "Sanhedrin", 2) is True

    def test_complex_title(self):
        """Test complex real-world title formats."""
        assert _match_video_title("Dr. Abramson - Sanhedrin 2 - Courts", "Sanhedrin", 2) is True
        assert _match_video_title("Jewish History: Sanhedrin 2", "Sanhedrin", 2) is True

    def test_masechta_not_present(self):
        """Test returns False when masechta is not in title."""
        assert _match_video_title("Berachos 2", "Sanhedrin", 2) is False

    def test_number_only_no_masechta(self):
        """Test returns False when only number is present."""
        assert _match_video_title("Video 2", "Sanhedrin", 2) is False

    def test_berachos_conversion(self):
        """Test with converted masechta name."""
        assert _match_video_title("Berachos 15 - Medieval Era", "Berachos", 15) is True


class TestVideoMatchingPatterns:
    """Tests for video title matching logic in full scraping context."""

    @pytest.mark.asyncio
    async def test_match_simple_format(self):
        """Test matching 'Masechta N' format."""
        html = '<a href="/p/1">Sanhedrin 2</a>'
        await self._test_match(html, "Sanhedrin", 2, True)

    @pytest.mark.asyncio
    async def test_match_with_daf_keyword(self):
        """Test matching 'Masechta Daf N' format."""
        html = '<a href="/p/1">Sanhedrin Daf 2</a>'
        await self._test_match(html, "Sanhedrin", 2, True)

    @pytest.mark.asyncio
    async def test_match_with_description(self):
        """Test matching 'Masechta N - Description' format."""
        html = '<a href="/p/1">Sanhedrin 2 - Courts and Justice</a>'
        await self._test_match(html, "Sanhedrin", 2, True)

    @pytest.mark.asyncio
    async def test_match_case_insensitive(self):
        """Test case-insensitive matching."""
        html = '<a href="/p/1">SANHEDRIN 2</a>'
        await self._test_match(html, "Sanhedrin", 2, True)

    @pytest.mark.asyncio
    async def test_no_match_wrong_daf(self):
        """Test no match for wrong daf number."""
        html = '<a href="/p/1">Sanhedrin 3</a>'
        await self._test_match(html, "Sanhedrin", 2, False)

    @pytest.mark.asyncio
    async def test_no_match_partial_number(self):
        """Test no match when daf is part of larger number."""
        html = '<a href="/p/1">Sanhedrin 22</a>'
        await self._test_match(html, "Sanhedrin", 2, False)

    async def _test_match(self, html: str, masechta: str, daf: int, should_match: bool):
        """Helper to test video matching."""
        full_html = f"""
        <html><body>
        {html}
        <a href="/p/999">Other Video</a>
        </body></html>
        """

        series_response = MagicMock()
        series_response.text = full_html
        series_response.raise_for_status = MagicMock()

        video_response = MagicMock()
        video_response.text = ALLDAF_VIDEO_PAGE_HTML
        video_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = [series_response, video_response]
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            daf_info = DafInfo(masechta=masechta, daf=daf)

            if should_match:
                video = await get_jewish_history_video(daf_info)
                assert video is not None
            else:
                with pytest.raises(ValueError, match="Video not found"):
                    await get_jewish_history_video(daf_info)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
