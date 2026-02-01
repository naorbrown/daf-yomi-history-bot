"""
Unit tests for broadcast state tracking in send_video.py

Tests the deduplication mechanism that prevents duplicate daily broadcasts.
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from send_video import (
    get_last_broadcast_date,
    save_last_broadcast_date,
    has_already_broadcast_today,
    is_within_send_window,
    SEND_HOUR,
    SEND_WINDOW_MINUTES_BEFORE,
    SEND_WINDOW_MINUTES_AFTER,
)


class TestGetLastBroadcastDate:
    """Tests for get_last_broadcast_date function."""

    def test_returns_none_when_file_not_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict("os.environ", {"GITHUB_WORKSPACE": tmpdir}):
                result = get_last_broadcast_date()
                assert result is None

    def test_returns_date_from_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / ".github" / "state"
            state_dir.mkdir(parents=True)
            broadcast_file = state_dir / "last_broadcast.json"
            broadcast_file.write_text(json.dumps({"date": "2026-02-01"}))

            with patch.dict("os.environ", {"GITHUB_WORKSPACE": tmpdir}):
                result = get_last_broadcast_date()
                assert result == "2026-02-01"

    def test_returns_none_on_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / ".github" / "state"
            state_dir.mkdir(parents=True)
            broadcast_file = state_dir / "last_broadcast.json"
            broadcast_file.write_text("invalid json")

            with patch.dict("os.environ", {"GITHUB_WORKSPACE": tmpdir}):
                result = get_last_broadcast_date()
                assert result is None


class TestSaveLastBroadcastDate:
    """Tests for save_last_broadcast_date function."""

    def test_creates_file_and_saves_date(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict("os.environ", {"GITHUB_WORKSPACE": tmpdir}):
                save_last_broadcast_date("2026-02-01")

                broadcast_file = Path(tmpdir) / ".github" / "state" / "last_broadcast.json"
                assert broadcast_file.exists()
                data = json.loads(broadcast_file.read_text())
                assert data["date"] == "2026-02-01"

    def test_overwrites_existing_date(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / ".github" / "state"
            state_dir.mkdir(parents=True)
            broadcast_file = state_dir / "last_broadcast.json"
            broadcast_file.write_text(json.dumps({"date": "2026-01-31"}))

            with patch.dict("os.environ", {"GITHUB_WORKSPACE": tmpdir}):
                save_last_broadcast_date("2026-02-01")

                data = json.loads(broadcast_file.read_text())
                assert data["date"] == "2026-02-01"


class TestHasAlreadyBroadcastToday:
    """Tests for has_already_broadcast_today function."""

    def test_returns_false_when_no_previous_broadcast(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict("os.environ", {"GITHUB_WORKSPACE": tmpdir}):
                with patch("send_video.datetime") as mock_datetime:
                    mock_now = MagicMock()
                    mock_now.strftime.return_value = "2026-02-01"
                    mock_datetime.now.return_value = mock_now

                    result = has_already_broadcast_today()
                    assert result is False

    def test_returns_true_when_already_broadcast_today(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / ".github" / "state"
            state_dir.mkdir(parents=True)
            broadcast_file = state_dir / "last_broadcast.json"
            broadcast_file.write_text(json.dumps({"date": "2026-02-01"}))

            with patch.dict("os.environ", {"GITHUB_WORKSPACE": tmpdir}):
                with patch("send_video.datetime") as mock_datetime:
                    mock_now = MagicMock()
                    mock_now.strftime.return_value = "2026-02-01"
                    mock_datetime.now.return_value = mock_now

                    result = has_already_broadcast_today()
                    assert result is True

    def test_returns_false_when_broadcast_was_yesterday(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / ".github" / "state"
            state_dir.mkdir(parents=True)
            broadcast_file = state_dir / "last_broadcast.json"
            broadcast_file.write_text(json.dumps({"date": "2026-01-31"}))

            with patch.dict("os.environ", {"GITHUB_WORKSPACE": tmpdir}):
                with patch("send_video.datetime") as mock_datetime:
                    mock_now = MagicMock()
                    mock_now.strftime.return_value = "2026-02-01"
                    mock_datetime.now.return_value = mock_now

                    result = has_already_broadcast_today()
                    assert result is False


class TestIsWithinSendWindow:
    """Tests for is_within_send_window function."""

    def test_within_window_at_6am(self):
        with patch("send_video.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.hour = 6
            mock_now.minute = 0
            mock_now.strftime.return_value = "06:00"
            mock_datetime.now.return_value = mock_now

            result = is_within_send_window()
            assert result is True

    def test_within_window_at_window_start(self):
        """Test at 5:00 AM (new wider window)."""
        with patch("send_video.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.hour = 5
            mock_now.minute = 0
            mock_now.strftime.return_value = "05:00"
            mock_datetime.now.return_value = mock_now

            result = is_within_send_window()
            assert result is True

    def test_within_window_at_window_end(self):
        """Test at 8:00 AM (new wider window end)."""
        with patch("send_video.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.hour = 8
            mock_now.minute = 0
            mock_now.strftime.return_value = "08:00"
            mock_datetime.now.return_value = mock_now

            result = is_within_send_window()
            assert result is True

    def test_outside_window_before(self):
        """Test at 4:59 AM (before window)."""
        with patch("send_video.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.hour = 4
            mock_now.minute = 59
            mock_now.strftime.return_value = "04:59"
            mock_datetime.now.return_value = mock_now

            result = is_within_send_window()
            assert result is False

    def test_outside_window_after(self):
        """Test at 8:01 AM (after window)."""
        with patch("send_video.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.hour = 8
            mock_now.minute = 1
            mock_now.strftime.return_value = "08:01"
            mock_datetime.now.return_value = mock_now

            result = is_within_send_window()
            assert result is False


class TestTimeWindowConstants:
    """Tests for time window constants."""

    def test_window_is_wide_enough(self):
        """Ensure the window is wide enough to handle GitHub Actions delays."""
        window_minutes = SEND_WINDOW_MINUTES_BEFORE + SEND_WINDOW_MINUTES_AFTER
        # At least 2 hours to handle typical cron delays
        assert window_minutes >= 120

    def test_send_hour_is_6am(self):
        """Ensure broadcasts are centered around 6 AM."""
        assert SEND_HOUR == 6
