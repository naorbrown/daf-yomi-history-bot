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
    send_todays_video,
    warm_cache,
    WELCOME_MESSAGE,
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

    def test_get_cached_video_no_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch(
                    "poll_commands.VIDEO_CACHE_FILE", Path(tmpdir) / "video_cache.json"
                ):
                    state = StateManager()
                    assert state.get_cached_video("2025-01-29") is None

    def test_get_cached_video_wrong_date(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "video_cache.json"
            cache_file.write_text(json.dumps({
                "date": "2025-01-28",
                "title": "Test Video",
                "page_url": "https://example.com",
                "video_url": "https://example.com/video.mp4",
                "masechta": "Berachos",
                "daf": 2,
            }))
            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.VIDEO_CACHE_FILE", cache_file):
                    state = StateManager()
                    # Different date - should return None
                    assert state.get_cached_video("2025-01-29") is None

    def test_get_cached_video_correct_date(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "video_cache.json"
            cache_data = {
                "date": "2025-01-29",
                "title": "Test Video",
                "page_url": "https://example.com",
                "video_url": "https://example.com/video.mp4",
                "masechta": "Berachos",
                "daf": 2,
            }
            cache_file.write_text(json.dumps(cache_data))
            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.VIDEO_CACHE_FILE", cache_file):
                    state = StateManager()
                    # Same date - should return cached data
                    result = state.get_cached_video("2025-01-29")
                    assert result is not None
                    assert result["title"] == "Test Video"
                    assert result["masechta"] == "Berachos"

    def test_save_video_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "video_cache.json"
            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.VIDEO_CACHE_FILE", cache_file):
                    state = StateManager()
                    cache_data = {
                        "date": "2025-01-29",
                        "title": "Test Video",
                        "page_url": "https://example.com",
                        "video_url": "https://example.com/video.mp4",
                        "masechta": "Berachos",
                        "daf": 2,
                    }
                    state.save_video_cache(cache_data)

                    # Verify file was written
                    assert cache_file.exists()
                    saved_data = json.loads(cache_file.read_text())
                    assert saved_data["date"] == "2025-01-29"
                    assert saved_data["title"] == "Test Video"


class TestSubscribers:
    """Tests for subscriber management."""

    def test_get_subscribers_no_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.SUBSCRIBERS_FILE", Path(tmpdir) / "subscribers.json"):
                    state = StateManager()
                    assert state.get_subscribers() == []

    def test_add_subscriber_new(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subs_file = Path(tmpdir) / "subscribers.json"
            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.SUBSCRIBERS_FILE", subs_file):
                    state = StateManager()
                    is_new = state.add_subscriber(123456)
                    assert is_new is True
                    assert 123456 in state.get_subscribers()

    def test_add_subscriber_duplicate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subs_file = Path(tmpdir) / "subscribers.json"
            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.SUBSCRIBERS_FILE", subs_file):
                    state = StateManager()
                    state.add_subscriber(123456)
                    is_new = state.add_subscriber(123456)
                    assert is_new is False
                    # Should only have one entry
                    assert state.get_subscribers().count(123456) == 1

    def test_multiple_subscribers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subs_file = Path(tmpdir) / "subscribers.json"
            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.SUBSCRIBERS_FILE", subs_file):
                    state = StateManager()
                    state.add_subscriber(111)
                    state.add_subscriber(222)
                    state.add_subscriber(333)
                    subs = state.get_subscribers()
                    assert len(subs) == 3
                    assert 111 in subs
                    assert 222 in subs
                    assert 333 in subs


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

    def test_welcome_message_contains_today_command(self):
        assert "/today" in WELCOME_MESSAGE

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
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            updates = await api.get_updates(offset=100)

            assert len(updates) == 2
            assert updates[0]["update_id"] == 123
            mock_instance.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_updates_with_none_offset(self):
        """Test get_updates works without offset (first run)."""
        api = TelegramAPI("test_token")

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "result": []}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
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
            mock_instance.post.return_value = mock_response
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


class TestProcessUpdates:
    """Tests for process_updates function."""

    @pytest.mark.asyncio
    async def test_offset_zero_uses_correct_value(self):
        """Test that offset=0 uses offset=1 (not None)."""
        from poll_commands import process_updates

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            rate_file = Path(tmpdir) / "rate_limits.json"

            # Set last_update_id to 0
            state_file.write_text(json.dumps({"last_update_id": 0}))

            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.STATE_FILE", state_file):
                    with patch("poll_commands.RATE_LIMIT_FILE", rate_file):
                        state = StateManager()

                        # Mock API
                        api = AsyncMock()
                        api.get_updates.return_value = []

                        await process_updates(api, state)

                        # Should call with offset=1, not None
                        api.get_updates.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_offset_one_when_no_state(self):
        """Test that offset=1 when no state exists (nachyomi-bot pattern)."""
        from poll_commands import process_updates

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            rate_file = Path(tmpdir) / "rate_limits.json"

            # Don't create state file - simulates first run

            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.STATE_FILE", state_file):
                    with patch("poll_commands.RATE_LIMIT_FILE", rate_file):
                        state = StateManager()

                        # Mock API
                        api = AsyncMock()
                        api.get_updates.return_value = []

                        await process_updates(api, state)

                        # nachyomi-bot pattern: offset = lastUpdateId + 1
                        # When no state exists, lastUpdateId defaults to 0
                        # So offset = 0 + 1 = 1
                        api.get_updates.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_continues_on_command_error(self):
        """Test that processing continues even if one command fails."""
        from poll_commands import process_updates

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            rate_file = Path(tmpdir) / "rate_limits.json"

            state_file.write_text(json.dumps({"last_update_id": 100}))

            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.STATE_FILE", state_file):
                    with patch("poll_commands.RATE_LIMIT_FILE", rate_file):
                        state = StateManager()

                        # Mock API with updates
                        api = AsyncMock()
                        api.get_updates.return_value = [
                            {
                                "update_id": 101,
                                "message": {
                                    "text": "/start",
                                    "chat": {"id": 123},
                                    "from": {"id": 456},
                                },
                            },
                            {
                                "update_id": 102,
                                "message": {
                                    "text": "/help",
                                    "chat": {"id": 789},
                                    "from": {"id": 999},
                                },
                            },
                        ]
                        # First send_message fails, second succeeds
                        api.send_message.side_effect = [
                            RuntimeError("Network error"),
                            {"ok": True},
                        ]

                        # Should not raise even though first command failed
                        processed = await process_updates(api, state)

                        # Both updates should be acknowledged (offset updated)
                        assert state.get_last_update_id() == 102
                        # Only one command successfully processed
                        assert processed == 1


class TestEndToEndFlow:
    """End-to-end tests simulating the full bot flow."""

    @pytest.mark.asyncio
    async def test_full_flow_first_run_with_pending_messages(self):
        """Test complete flow on first run with pending messages."""
        from poll_commands import main

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            rate_file = Path(tmpdir) / "rate_limits.json"
            cache_file = Path(tmpdir) / "video_cache.json"
            # Pre-warm cache for instant responses
            cache_data = {
                "date": "2025-01-29",
                "title": "Test Video",
                "page_url": "https://alldaf.org/p/123",
                "video_url": "https://cdn.jwplayer.com/videos/abc.mp4",
                "masechta": "Berachos",
                "daf": 2,
            }
            cache_file.write_text(json.dumps(cache_data))

            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.STATE_FILE", state_file):
                    with patch("poll_commands.RATE_LIMIT_FILE", rate_file):
                        with patch("poll_commands.VIDEO_CACHE_FILE", cache_file):
                            with patch("poll_commands.datetime") as mock_datetime:
                                mock_now = MagicMock()
                                mock_now.strftime.return_value = "2025-01-29"
                                mock_datetime.now.return_value = mock_now

                                with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "test_token"}):
                                    with patch("httpx.AsyncClient") as mock_client:
                                        mock_instance = AsyncMock()
                                        mock_instance.__aenter__.return_value = mock_instance
                                        mock_instance.__aexit__.return_value = None
                                        mock_client.return_value = mock_instance

                                        delete_webhook_response = MagicMock(
                                            json=lambda: {"ok": True, "result": True},
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
                                                    },
                                                ],
                                            },
                                            raise_for_status=MagicMock(),
                                        )
                                        send_response = MagicMock(
                                            json=lambda: {"ok": True, "result": {}},
                                            raise_for_status=MagicMock(),
                                        )

                                        # deleteWebhook, getUpdates, sendVideo
                                        mock_instance.post.side_effect = [
                                            delete_webhook_response,
                                            get_updates_response,
                                            send_response,
                                        ]

                                        result = await main()

                                        assert result == 0
                                        assert state_file.exists()
                                        data = json.loads(state_file.read_text())
                                        assert data["last_update_id"] == 100

    @pytest.mark.asyncio
    async def test_full_flow_subsequent_run(self):
        """Test complete flow on subsequent run with existing state."""
        from poll_commands import main

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            rate_file = Path(tmpdir) / "rate_limits.json"
            cache_file = Path(tmpdir) / "video_cache.json"

            state_file.write_text(json.dumps({"last_update_id": 100}))
            cache_data = {
                "date": "2025-01-29",
                "title": "Test Video",
                "page_url": "https://alldaf.org/p/123",
                "video_url": "https://cdn.jwplayer.com/videos/abc.mp4",
                "masechta": "Berachos",
                "daf": 2,
            }
            cache_file.write_text(json.dumps(cache_data))

            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.STATE_FILE", state_file):
                    with patch("poll_commands.RATE_LIMIT_FILE", rate_file):
                        with patch("poll_commands.VIDEO_CACHE_FILE", cache_file):
                            with patch("poll_commands.datetime") as mock_datetime:
                                mock_now = MagicMock()
                                mock_now.strftime.return_value = "2025-01-29"
                                mock_datetime.now.return_value = mock_now

                                with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "test_token"}):
                                    with patch("httpx.AsyncClient") as mock_client:
                                        mock_instance = AsyncMock()
                                        mock_instance.__aenter__.return_value = mock_instance
                                        mock_instance.__aexit__.return_value = None
                                        mock_client.return_value = mock_instance

                                        delete_webhook_response = MagicMock(
                                            json=lambda: {"ok": True, "result": True},
                                            raise_for_status=MagicMock(),
                                        )
                                        get_updates_response = MagicMock(
                                            json=lambda: {
                                                "ok": True,
                                                "result": [
                                                    {
                                                        "update_id": 101,
                                                        "message": {
                                                            "text": "/today",
                                                            "chat": {"id": 789},
                                                            "from": {"id": 111},
                                                        },
                                                    }
                                                ],
                                            },
                                            raise_for_status=MagicMock(),
                                        )
                                        send_response = MagicMock(
                                            json=lambda: {"ok": True, "result": {}},
                                            raise_for_status=MagicMock(),
                                        )

                                        mock_instance.post.side_effect = [
                                            delete_webhook_response,
                                            get_updates_response,
                                            send_response,
                                        ]

                                        result = await main()

                                        assert result == 0
                                        data = json.loads(state_file.read_text())
                                        assert data["last_update_id"] == 101


class TestSendTodaysVideo:
    """Tests for send_todays_video function."""

    @pytest.mark.asyncio
    async def test_sends_cached_video(self):
        """Test that cached video is sent without external API calls."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "video_cache.json"
            cache_data = {
                "date": "2025-01-29",
                "title": "Test Video",
                "page_url": "https://alldaf.org/p/123",
                "video_url": "https://cdn.jwplayer.com/videos/abc.mp4",
                "masechta": "Berachos",
                "daf": 2,
            }
            cache_file.write_text(json.dumps(cache_data))

            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.VIDEO_CACHE_FILE", cache_file):
                    with patch("poll_commands.datetime") as mock_datetime:
                        # Mock Israel timezone time
                        mock_now = MagicMock()
                        mock_now.strftime.return_value = "2025-01-29"
                        mock_datetime.now.return_value = mock_now

                        state = StateManager()
                        api = AsyncMock()
                        api.send_video.return_value = {"ok": True}

                        result = await send_todays_video(api, 123, state, 456)

                        assert result is True
                        api.send_video.assert_called_once()
                        # Verify caption contains expected info
                        call_args = api.send_video.call_args
                        assert "Berachos 2" in call_args[0][2]

    @pytest.mark.asyncio
    async def test_sends_error_on_failure(self):
        """Test that error message is sent when video fetch fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.VIDEO_CACHE_FILE", Path(tmpdir) / "cache.json"):
                    with patch("poll_commands.datetime") as mock_datetime:
                        mock_now = MagicMock()
                        mock_now.strftime.return_value = "2025-01-29"
                        mock_datetime.now.return_value = mock_now

                        with patch("poll_commands.get_todays_daf") as mock_daf:
                            mock_daf.side_effect = Exception("API error")

                            state = StateManager()
                            api = AsyncMock()

                            result = await send_todays_video(api, 123, state, 456)

                            assert result is False
                            api.send_message.assert_called_once()
                            # Check error message was sent
                            call_args = api.send_message.call_args
                            assert "alldaf.org" in call_args[0][1].lower()


class TestWarmCache:
    """Tests for warm_cache function."""

    @pytest.mark.asyncio
    async def test_warms_cold_cache(self):
        """Test that warm_cache fetches and caches video when cache is cold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "video_cache.json"

            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.VIDEO_CACHE_FILE", cache_file):
                    with patch("poll_commands.datetime") as mock_datetime:
                        mock_now = MagicMock()
                        mock_now.strftime.return_value = "2025-01-29"
                        mock_datetime.now.return_value = mock_now

                        with patch("poll_commands.get_todays_daf") as mock_daf:
                            with patch("poll_commands.get_jewish_history_video") as mock_video:
                                mock_daf.return_value = DafInfo(masechta="Berachos", daf=2)
                                mock_video.return_value = VideoInfo(
                                    title="Test Video",
                                    page_url="https://alldaf.org/p/123",
                                    video_url="https://cdn.jwplayer.com/videos/abc.mp4",
                                    masechta="Berachos",
                                    daf=2,
                                )

                                result = await warm_cache()

                                assert result == 0
                                assert cache_file.exists()
                                cached = json.loads(cache_file.read_text())
                                assert cached["date"] == "2025-01-29"
                                assert cached["title"] == "Test Video"

    @pytest.mark.asyncio
    async def test_skips_warm_cache(self):
        """Test that warm_cache skips if cache is already warm."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "video_cache.json"
            cache_data = {
                "date": "2025-01-29",
                "title": "Already Cached",
                "page_url": "https://alldaf.org/p/123",
                "video_url": "https://cdn.jwplayer.com/videos/abc.mp4",
                "masechta": "Berachos",
                "daf": 2,
            }
            cache_file.write_text(json.dumps(cache_data))

            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.VIDEO_CACHE_FILE", cache_file):
                    with patch("poll_commands.datetime") as mock_datetime:
                        mock_now = MagicMock()
                        mock_now.strftime.return_value = "2025-01-29"
                        mock_datetime.now.return_value = mock_now

                        with patch("poll_commands.get_todays_daf") as mock_daf:
                            result = await warm_cache()

                            assert result == 0
                            # Should not have fetched new daf
                            mock_daf.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_fetch_error(self):
        """Test that warm_cache returns error code on failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.VIDEO_CACHE_FILE", Path(tmpdir) / "cache.json"):
                    with patch("poll_commands.datetime") as mock_datetime:
                        mock_now = MagicMock()
                        mock_now.strftime.return_value = "2025-01-29"
                        mock_datetime.now.return_value = mock_now

                        with patch("poll_commands.get_todays_daf") as mock_daf:
                            mock_daf.side_effect = Exception("Network error")

                            result = await warm_cache()

                            assert result == 1


class TestCommandFlow:
    """Tests for complete command handling flow."""

    @pytest.mark.asyncio
    async def test_start_sends_welcome_and_video(self):
        """Test that /start sends welcome message followed by today's video."""
        from poll_commands import handle_command

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "video_cache.json"
            rate_file = Path(tmpdir) / "rates.json"
            cache_data = {
                "date": "2025-01-29",
                "title": "Test Video",
                "page_url": "https://alldaf.org/p/123",
                "video_url": "https://cdn.jwplayer.com/videos/abc.mp4",
                "masechta": "Berachos",
                "daf": 2,
            }
            cache_file.write_text(json.dumps(cache_data))

            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.VIDEO_CACHE_FILE", cache_file):
                    with patch("poll_commands.RATE_LIMIT_FILE", rate_file):
                        with patch("poll_commands.datetime") as mock_datetime:
                            mock_now = MagicMock()
                            mock_now.strftime.return_value = "2025-01-29"
                            mock_datetime.now.return_value = mock_now

                            state = StateManager()
                            rate_limiter = RateLimiter(state)
                            api = AsyncMock()
                            api.send_message.return_value = {"ok": True}
                            api.send_video.return_value = {"ok": True}

                            await handle_command(api, 123, "start", rate_limiter, 456, state)

                            # Should send welcome message first, then video
                            assert api.send_message.call_count == 1
                            assert api.send_video.call_count == 1
                            # First call should be welcome message
                            welcome_call = api.send_message.call_args_list[0]
                            assert "Welcome" in welcome_call[0][1]

    @pytest.mark.asyncio
    async def test_help_sends_video(self):
        """Test that /help sends today's video (same as /today)."""
        from poll_commands import handle_command

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "video_cache.json"
            rate_file = Path(tmpdir) / "rates.json"
            cache_data = {
                "date": "2025-01-29",
                "title": "Test Video",
                "page_url": "https://alldaf.org/p/123",
                "video_url": "https://cdn.jwplayer.com/videos/abc.mp4",
                "masechta": "Berachos",
                "daf": 2,
            }
            cache_file.write_text(json.dumps(cache_data))

            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.VIDEO_CACHE_FILE", cache_file):
                    with patch("poll_commands.RATE_LIMIT_FILE", rate_file):
                        with patch("poll_commands.datetime") as mock_datetime:
                            mock_now = MagicMock()
                            mock_now.strftime.return_value = "2025-01-29"
                            mock_datetime.now.return_value = mock_now

                            state = StateManager()
                            rate_limiter = RateLimiter(state)
                            api = AsyncMock()
                            api.send_video.return_value = {"ok": True}

                            await handle_command(api, 123, "help", rate_limiter, 456, state)

                            # Should send video
                            api.send_video.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_limit_applies_to_help_and_today(self):
        """Test that rate limiting applies to /help and /today but not /start."""
        from poll_commands import handle_command

        with tempfile.TemporaryDirectory() as tmpdir:
            rate_file = Path(tmpdir) / "rates.json"

            with patch("poll_commands.STATE_DIR", Path(tmpdir)):
                with patch("poll_commands.RATE_LIMIT_FILE", rate_file):
                    state = StateManager()
                    rate_limiter = RateLimiter(state)
                    api = AsyncMock()
                    api.send_message.return_value = {"ok": True}

                    # Exhaust rate limit
                    for _ in range(5):
                        rate_limiter.is_allowed(456)

                    # /start should still work (not rate limited)
                    with patch("poll_commands.send_todays_video", new_callable=AsyncMock):
                        await handle_command(api, 123, "start", rate_limiter, 456, state)
                        # Should have sent welcome (not rate limit message)
                        assert "Welcome" in api.send_message.call_args[0][1]

                    api.reset_mock()

                    # /today should be rate limited
                    await handle_command(api, 123, "today", rate_limiter, 456, state)
                    assert "too many" in api.send_message.call_args[0][1].lower()
