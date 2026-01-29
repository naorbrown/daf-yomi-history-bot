"""
Unit tests for scripts/poll_commands.py

Tests the command polling functionality used by GitHub Actions.
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

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
    initialize_state_if_needed,
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

    @pytest.mark.asyncio
    async def test_get_updates_success(self):
        """Test get_updates returns updates on success."""
        api = TelegramAPI("test_token")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "result": [
                {"update_id": 123, "message": {"text": "/start"}},
                {"update_id": 124, "message": {"text": "/today"}},
            ],
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            updates = await api.get_updates(offset=100)

            assert len(updates) == 2
            assert updates[0]["update_id"] == 123
            mock_instance.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_updates_with_none_offset(self):
        """Test get_updates works without offset (first run)."""
        api = TelegramAPI("test_token")

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "result": []}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            updates = await api.get_updates(offset=None)

            assert updates == []

    @pytest.mark.asyncio
    async def test_get_updates_api_error(self):
        """Test get_updates raises on API error."""
        api = TelegramAPI("test_token")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": False,
            "description": "Unauthorized",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(RuntimeError, match="Telegram API error"):
                await api.get_updates()

    @pytest.mark.asyncio
    async def test_send_message_success(self):
        """Test send_message returns data on success."""
        api = TelegramAPI("test_token")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "result": {"message_id": 456},
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await api.send_message(123, "Hello!")

            assert result["ok"] is True
            assert result["result"]["message_id"] == 456
            mock_instance.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_api_error(self):
        """Test send_message raises on API error."""
        api = TelegramAPI("test_token")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": False,
            "description": "Bad Request: chat not found",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(RuntimeError, match="Telegram API error"):
                await api.send_message(123, "Hello!")

    @pytest.mark.asyncio
    async def test_send_video_success(self):
        """Test send_video returns data on success."""
        api = TelegramAPI("test_token")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "result": {"message_id": 789},
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await api.send_video(
                123, "https://example.com/video.mp4", "Caption"
            )

            assert result["ok"] is True
            assert result["result"]["message_id"] == 789

    @pytest.mark.asyncio
    async def test_send_video_api_error(self):
        """Test send_video raises on API error."""
        api = TelegramAPI("test_token")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": False,
            "description": "Bad Request: wrong file identifier",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(RuntimeError, match="Telegram API error"):
                await api.send_video(123, "https://example.com/video.mp4", "Caption")


class TestInitializeState:
    """Tests for initialize_state_if_needed function."""

    @pytest.mark.asyncio
    async def test_skips_if_state_exists(self):
        """Test initialization is skipped if state already exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            state_file.write_text(json.dumps({"last_update_id": 100}))

            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.STATE_FILE", state_file):
                    state = StateManager()
                    api = MagicMock()

                    await initialize_state_if_needed(api, state)

                    # API should not be called
                    api.get_updates.assert_not_called()

    @pytest.mark.asyncio
    async def test_initializes_with_updates(self):
        """Test state is initialized with max update_id from pending updates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"

            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.STATE_FILE", state_file):
                    state = StateManager()

                    # Mock API to return some updates
                    api = AsyncMock()
                    api.get_updates.return_value = [
                        {"update_id": 100},
                        {"update_id": 150},
                        {"update_id": 125},
                    ]

                    await initialize_state_if_needed(api, state)

                    # State should be set to max update_id
                    assert state.get_last_update_id() == 150

    @pytest.mark.asyncio
    async def test_initializes_without_updates(self):
        """Test state is initialized to 0 when no pending updates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"

            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.STATE_FILE", state_file):
                    state = StateManager()

                    # Mock API to return no updates
                    api = AsyncMock()
                    api.get_updates.return_value = []

                    await initialize_state_if_needed(api, state)

                    # State should be set to 0
                    assert state.get_last_update_id() == 0

    @pytest.mark.asyncio
    async def test_handles_api_error_gracefully(self):
        """Test initialization handles API errors without crashing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"

            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.STATE_FILE", state_file):
                    state = StateManager()

                    # Mock API to raise an error
                    api = AsyncMock()
                    api.get_updates.side_effect = RuntimeError("API Error")

                    # Should not raise
                    await initialize_state_if_needed(api, state)

                    # State should remain None (not set)
                    assert state.get_last_update_id() is None
