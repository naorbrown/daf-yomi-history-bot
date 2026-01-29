"""
Unit tests for scripts/poll_commands.py

Tests the command polling functionality used by GitHub Actions.
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from poll_commands import (
    DafInfo,
    VideoInfo,
    TelegramAPI,
    StateManager,
    RateLimiter,
    parse_command,
    convert_masechta_name,
    WELCOME_MESSAGE,
    HELP_MESSAGE,
    ERROR_MESSAGE,
    RATE_LIMITED_MESSAGE,
)


class TestParseCommand:
    """Tests for parse_command function."""

    def test_parse_start_command(self):
        assert parse_command("/start") == "start"

    def test_parse_help_command(self):
        assert parse_command("/help") == "help"

    def test_parse_today_command(self):
        assert parse_command("/today") == "today"

    def test_parse_command_with_bot_mention(self):
        assert parse_command("/start@DafHistoryBot") == "start"

    def test_parse_command_case_insensitive(self):
        assert parse_command("/START") == "start"
        assert parse_command("/Help") == "help"

    def test_parse_unknown_command_returns_name(self):
        # parse_command extracts the command name without validation
        # handle_command decides what to do with unknown commands
        assert parse_command("/unknown") == "unknown"

    def test_parse_non_command(self):
        assert parse_command("hello") is None

    def test_parse_empty(self):
        assert parse_command("") is None

    def test_parse_none(self):
        assert parse_command(None) is None

    def test_parse_whitespace(self):
        assert parse_command("   ") is None

    def test_parse_slash_only(self):
        assert parse_command("/") is None


class TestConvertMasechtaName:
    """Tests for masechta name conversion."""

    def test_convert_berakhot(self):
        assert convert_masechta_name("Berakhot") == "Berachos"

    def test_convert_shabbat(self):
        assert convert_masechta_name("Shabbat") == "Shabbos"

    def test_convert_unknown_returns_original(self):
        assert convert_masechta_name("Unknown") == "Unknown"

    def test_convert_already_alldaf_format(self):
        assert convert_masechta_name("Berachos") == "Berachos"


class TestDafInfo:
    """Tests for DafInfo dataclass."""

    def test_create_daf_info(self):
        daf = DafInfo(masechta="Berachos", daf=2)
        assert daf.masechta == "Berachos"
        assert daf.daf == 2


class TestVideoInfo:
    """Tests for VideoInfo dataclass."""

    def test_create_video_info(self):
        video = VideoInfo(
            title="Test Title",
            page_url="https://example.com",
            video_url="https://example.com/video.mp4",
            masechta="Berachos",
            daf=2,
        )
        assert video.title == "Test Title"
        assert video.video_url == "https://example.com/video.mp4"

    def test_video_info_with_none_url(self):
        video = VideoInfo(
            title="Test",
            page_url="https://example.com",
            video_url=None,
            masechta="Berachos",
            daf=2,
        )
        assert video.video_url is None


class TestStateManager:
    """Tests for StateManager class."""

    def test_get_last_update_id_no_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.STATE_FILE", Path(tmpdir) / "state.json"):
                    state = StateManager()
                    assert state.get_last_update_id() is None

    def test_set_and_get_last_update_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.STATE_FILE", state_file):
                    state = StateManager()
                    state.set_last_update_id(12345)

                    # Read directly from file
                    data = json.loads(state_file.read_text())
                    assert data["last_update_id"] == 12345

                    # Also verify getter
                    assert state.get_last_update_id() == 12345

    def test_get_rate_limits_no_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch(
                    "poll_commands.RATE_LIMIT_FILE", Path(tmpdir) / "rates.json"
                ):
                    state = StateManager()
                    assert state.get_rate_limits() == {}


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_allows_first_request(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rate_file = Path(tmpdir) / "rates.json"
            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.RATE_LIMIT_FILE", rate_file):
                    state = StateManager()
                    limiter = RateLimiter(state)
                    assert limiter.is_allowed(123) is True

    def test_allows_multiple_requests_within_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rate_file = Path(tmpdir) / "rates.json"
            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.RATE_LIMIT_FILE", rate_file):
                    state = StateManager()
                    limiter = RateLimiter(state)
                    for _ in range(5):
                        assert limiter.is_allowed(123) is True

    def test_blocks_requests_over_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rate_file = Path(tmpdir) / "rates.json"
            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.RATE_LIMIT_FILE", rate_file):
                    state = StateManager()
                    limiter = RateLimiter(state)
                    # Use up all requests
                    for _ in range(5):
                        limiter.is_allowed(123)
                    # Next should be blocked
                    assert limiter.is_allowed(123) is False

    def test_per_user_isolation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rate_file = Path(tmpdir) / "rates.json"
            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.RATE_LIMIT_FILE", rate_file):
                    state = StateManager()
                    limiter = RateLimiter(state)
                    # Exhaust user 123's limit
                    for _ in range(5):
                        limiter.is_allowed(123)
                    # User 456 should still be allowed
                    assert limiter.is_allowed(456) is True


class TestMessages:
    """Tests for bot messages."""

    def test_welcome_message_not_empty(self):
        assert len(WELCOME_MESSAGE) > 0

    def test_welcome_message_contains_commands(self):
        assert "/today" in WELCOME_MESSAGE
        assert "/help" in WELCOME_MESSAGE

    def test_help_message_not_empty(self):
        assert len(HELP_MESSAGE) > 0

    def test_help_message_contains_commands(self):
        assert "/today" in HELP_MESSAGE
        assert "/help" in HELP_MESSAGE

    def test_error_message_contains_link(self):
        assert "alldaf.org" in ERROR_MESSAGE.lower()

    def test_rate_limited_message_not_empty(self):
        assert len(RATE_LIMITED_MESSAGE) > 0


class TestTelegramAPI:
    """Tests for TelegramAPI class."""

    def test_api_init(self):
        api = TelegramAPI("test_token")
        assert api.token == "test_token"
        assert "test_token" in api.base_url

    def test_api_base_url_format(self):
        api = TelegramAPI("123456:ABC-DEF")
        assert api.base_url == "https://api.telegram.org/bot123456:ABC-DEF"
