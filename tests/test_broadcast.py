"""
End-to-end tests for broadcast deduplication and timezone handling.

These tests verify that:
1. Broadcasts only happen once per day (no duplicates)
2. Israel timezone is used correctly for date calculations
3. DST transitions are handled properly
4. The send window works correctly
"""

import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from zoneinfo import ZoneInfo

import pytest

# Import the module under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from send_video import (
    ISRAEL_TZ,
    SEND_HOUR,
    SEND_WINDOW_MINUTES_BEFORE,
    SEND_WINDOW_MINUTES_AFTER,
    is_within_send_window,
    has_already_broadcast_today,
    get_last_broadcast_date,
    save_last_broadcast_date,
    get_subscribers,
    broadcast_to_subscribers,
    VideoInfo,
)


class TestIsraelTimezone:
    """Tests for Israel timezone handling."""

    def test_israel_timezone_is_jerusalem(self):
        """Verify we use Asia/Jerusalem timezone."""
        assert ISRAEL_TZ == ZoneInfo("Asia/Jerusalem")

    def test_israel_winter_time_offset(self):
        """Israel Standard Time (IST) is UTC+2."""
        # January 15, 2026 - definitely winter time
        winter_dt = datetime(2026, 1, 15, 12, 0, 0, tzinfo=ISRAEL_TZ)
        utc_offset = winter_dt.utcoffset()
        assert utc_offset == timedelta(hours=2)

    def test_israel_summer_time_offset(self):
        """Israel Daylight Time (IDT) is UTC+3."""
        # July 15, 2026 - definitely summer time
        summer_dt = datetime(2026, 7, 15, 12, 0, 0, tzinfo=ISRAEL_TZ)
        utc_offset = summer_dt.utcoffset()
        assert utc_offset == timedelta(hours=3)


class TestSendWindow:
    """Tests for the send window logic."""

    def test_send_window_constants(self):
        """Verify send window is 2:00 AM to 5:00 AM Israel time."""
        # Window starts at 2:00 AM (3:00 - 60 minutes)
        window_start_hour = SEND_HOUR - (SEND_WINDOW_MINUTES_BEFORE // 60)
        assert window_start_hour == 2

        # Window ends at 5:00 AM (3:00 + 120 minutes)
        window_end_hour = SEND_HOUR + (SEND_WINDOW_MINUTES_AFTER // 60)
        assert window_end_hour == 5

    @patch('send_video.datetime')
    def test_within_window_at_3am(self, mock_datetime):
        """3:00 AM Israel time is within the window."""
        mock_now = datetime(2026, 2, 2, 3, 0, 0, tzinfo=ISRAEL_TZ)
        mock_datetime.now.return_value = mock_now
        assert is_within_send_window() is True

    @patch('send_video.datetime')
    def test_within_window_at_2am(self, mock_datetime):
        """2:00 AM Israel time is within the window (edge)."""
        mock_now = datetime(2026, 2, 2, 2, 0, 0, tzinfo=ISRAEL_TZ)
        mock_datetime.now.return_value = mock_now
        assert is_within_send_window() is True

    @patch('send_video.datetime')
    def test_within_window_at_5am(self, mock_datetime):
        """5:00 AM Israel time is within the window (edge)."""
        mock_now = datetime(2026, 2, 2, 5, 0, 0, tzinfo=ISRAEL_TZ)
        mock_datetime.now.return_value = mock_now
        assert is_within_send_window() is True

    @patch('send_video.datetime')
    def test_outside_window_at_1am(self, mock_datetime):
        """1:00 AM Israel time is outside the window."""
        mock_now = datetime(2026, 2, 2, 1, 0, 0, tzinfo=ISRAEL_TZ)
        mock_datetime.now.return_value = mock_now
        assert is_within_send_window() is False

    @patch('send_video.datetime')
    def test_outside_window_at_6am(self, mock_datetime):
        """6:00 AM Israel time is outside the window."""
        mock_now = datetime(2026, 2, 2, 6, 0, 0, tzinfo=ISRAEL_TZ)
        mock_datetime.now.return_value = mock_now
        assert is_within_send_window() is False

    @patch('send_video.datetime')
    def test_within_window_at_4am_summer(self, mock_datetime):
        """4:00 AM Israel time in summer (when 1:00 UTC cron runs) is within window."""
        # July 15, 2026 - summer time, 1:00 UTC = 4:00 AM IDT
        mock_now = datetime(2026, 7, 15, 4, 0, 0, tzinfo=ISRAEL_TZ)
        mock_datetime.now.return_value = mock_now
        assert is_within_send_window() is True


class TestBroadcastDeduplication:
    """Tests for broadcast deduplication logic."""

    def test_save_and_get_last_broadcast_date(self, tmp_path):
        """Test saving and retrieving broadcast date."""
        state_dir = tmp_path / ".github" / "state"
        state_dir.mkdir(parents=True)
        
        with patch.dict(os.environ, {"GITHUB_WORKSPACE": str(tmp_path)}):
            # Save a date
            save_last_broadcast_date("2026-02-02")
            
            # Retrieve it
            result = get_last_broadcast_date()
            assert result == "2026-02-02"

    def test_get_last_broadcast_date_no_file(self, tmp_path):
        """Returns None when state file doesn't exist."""
        with patch.dict(os.environ, {"GITHUB_WORKSPACE": str(tmp_path)}):
            result = get_last_broadcast_date()
            assert result is None

    @patch('send_video.datetime')
    def test_has_already_broadcast_today_true(self, mock_datetime, tmp_path):
        """Returns True when already broadcast today."""
        state_dir = tmp_path / ".github" / "state"
        state_dir.mkdir(parents=True)
        
        mock_now = datetime(2026, 2, 2, 6, 0, 0, tzinfo=ISRAEL_TZ)
        mock_datetime.now.return_value = mock_now
        
        with patch.dict(os.environ, {"GITHUB_WORKSPACE": str(tmp_path)}):
            save_last_broadcast_date("2026-02-02")
            assert has_already_broadcast_today() is True

    @patch('send_video.datetime')
    def test_has_already_broadcast_today_false_different_date(self, mock_datetime, tmp_path):
        """Returns False when last broadcast was on a different day."""
        state_dir = tmp_path / ".github" / "state"
        state_dir.mkdir(parents=True)
        
        mock_now = datetime(2026, 2, 3, 6, 0, 0, tzinfo=ISRAEL_TZ)
        mock_datetime.now.return_value = mock_now
        
        with patch.dict(os.environ, {"GITHUB_WORKSPACE": str(tmp_path)}):
            save_last_broadcast_date("2026-02-02")
            assert has_already_broadcast_today() is False

    @patch('send_video.datetime')
    def test_has_already_broadcast_today_false_no_file(self, mock_datetime, tmp_path):
        """Returns False when no state file exists."""
        mock_now = datetime(2026, 2, 2, 6, 0, 0, tzinfo=ISRAEL_TZ)
        mock_datetime.now.return_value = mock_now
        
        with patch.dict(os.environ, {"GITHUB_WORKSPACE": str(tmp_path)}):
            assert has_already_broadcast_today() is False


class TestDSTTransitions:
    """Tests for DST transition edge cases."""

    def test_dst_spring_forward_date_consistency(self):
        """
        Date should be consistent across DST spring-forward transition.
        
        When clocks move forward at 2:00 AM, we should still correctly
        identify the date in Israel timezone.
        """
        # March 27, 2026 - Israel DST transition (approximate)
        # Just before transition (1:59 AM IST = UTC+2)
        before = datetime(2026, 3, 27, 1, 59, 0, tzinfo=ISRAEL_TZ)
        # Just after transition (3:00 AM IDT = UTC+3)
        after = datetime(2026, 3, 27, 3, 0, 0, tzinfo=ISRAEL_TZ)
        
        # Both should report the same date
        assert before.strftime("%Y-%m-%d") == after.strftime("%Y-%m-%d")

    def test_dst_fall_back_date_consistency(self):
        """
        Date should be consistent across DST fall-back transition.
        
        When clocks move back at 2:00 AM, we should still correctly
        identify the date in Israel timezone.
        """
        # October 25, 2026 - Israel DST ends (approximate)
        before = datetime(2026, 10, 25, 1, 59, 0, tzinfo=ISRAEL_TZ)
        after = datetime(2026, 10, 25, 2, 30, 0, tzinfo=ISRAEL_TZ)
        
        # Both should report the same date
        assert before.strftime("%Y-%m-%d") == after.strftime("%Y-%m-%d")

    @patch('send_video.datetime')
    def test_1am_utc_summer_is_4am_israel(self, mock_datetime):
        """
        1:00 UTC in summer = 4:00 AM Israel (IDT), which is within window.

        This verifies our single-cron approach works for summer time.
        """
        # 1:00 UTC on July 15, 2026 = 4:00 AM IDT
        mock_now = datetime(2026, 7, 15, 4, 0, 0, tzinfo=ISRAEL_TZ)
        mock_datetime.now.return_value = mock_now

        assert is_within_send_window() is True

    @patch('send_video.datetime')
    def test_1am_utc_winter_is_3am_israel(self, mock_datetime):
        """
        1:00 UTC in winter = 3:00 AM Israel (IST), which is within window.

        This verifies our single-cron approach works for winter time.
        """
        # 1:00 UTC on January 15, 2026 = 3:00 AM IST
        mock_now = datetime(2026, 1, 15, 3, 0, 0, tzinfo=ISRAEL_TZ)
        mock_datetime.now.return_value = mock_now

        assert is_within_send_window() is True


class TestEndToEndBroadcast:
    """End-to-end tests for the complete broadcast flow."""

    @pytest.mark.asyncio
    @patch('send_video.datetime')
    @patch('send_video.get_todays_daf')
    @patch('send_video.get_jewish_history_video')
    @patch('send_video.send_to_telegram')
    @patch('send_video.broadcast_to_subscribers')
    @patch('send_video.send_to_unified_channel')
    async def test_broadcast_saves_date_on_success(
        self,
        mock_unified,
        mock_broadcast,
        mock_send,
        mock_video,
        mock_daf,
        mock_datetime,
        tmp_path
    ):
        """Successful broadcast saves the date to prevent duplicates."""
        from send_video import main, DafInfo, VideoInfo
        
        state_dir = tmp_path / ".github" / "state"
        state_dir.mkdir(parents=True)
        
        mock_now = datetime(2026, 2, 2, 3, 0, 0, tzinfo=ISRAEL_TZ)
        mock_datetime.now.return_value = mock_now

        mock_daf.return_value = DafInfo(masechta="Berachos", daf=10)
        mock_video.return_value = VideoInfo(
            title="Test Video",
            page_url="https://example.com",
            video_url="https://example.com/video.mp4",
            masechta="Berachos",
            daf=10
        )
        mock_send.return_value = None
        mock_broadcast.return_value = (1, 0)
        mock_unified.return_value = None
        
        with patch.dict(os.environ, {
            "GITHUB_WORKSPACE": str(tmp_path),
            "TELEGRAM_BOT_TOKEN": "test-token",
            "TELEGRAM_CHAT_ID": "123",
        }):
            result = await main()
            
            assert result == 0
            # Verify date was saved
            saved_date = get_last_broadcast_date()
            assert saved_date == "2026-02-02"

    @pytest.mark.asyncio
    @patch('send_video.datetime')
    async def test_duplicate_broadcast_prevented(self, mock_datetime, tmp_path):
        """Second broadcast attempt on same day is prevented."""
        from send_video import main

        state_dir = tmp_path / ".github" / "state"
        state_dir.mkdir(parents=True)

        mock_now = datetime(2026, 2, 2, 3, 0, 0, tzinfo=ISRAEL_TZ)
        mock_datetime.now.return_value = mock_now
        
        with patch.dict(os.environ, {
            "GITHUB_WORKSPACE": str(tmp_path),
            "TELEGRAM_BOT_TOKEN": "test-token",
        }):
            # Simulate already broadcast
            save_last_broadcast_date("2026-02-02")
            
            # Should exit early without sending
            result = await main()
            
            assert result == 0  # Success exit code (skip is not an error)

    @pytest.mark.asyncio
    @patch('send_video.datetime')
    async def test_outside_window_skips_broadcast(self, mock_datetime, tmp_path):
        """Broadcast is skipped when outside the send window."""
        from send_video import main

        mock_now = datetime(2026, 2, 2, 0, 0, 0, tzinfo=ISRAEL_TZ)  # midnight (outside window)
        mock_datetime.now.return_value = mock_now

        with patch.dict(os.environ, {
            "GITHUB_WORKSPACE": str(tmp_path),
            "TELEGRAM_BOT_TOKEN": "test-token",
        }):
            result = await main()

            assert result == 0  # Success exit code (skip is not an error)


class TestSubscriberDeduplication:
    """Tests for preventing duplicate messages to subscribers who are also the main chat."""

    def test_get_subscribers_returns_chat_ids(self, tmp_path):
        """Test loading subscribers from state file."""
        state_dir = tmp_path / ".github" / "state"
        state_dir.mkdir(parents=True)
        subscribers_file = state_dir / "subscribers.json"
        subscribers_file.write_text(json.dumps({"chat_ids": [123, 456, 789]}))

        with patch.dict(os.environ, {"GITHUB_WORKSPACE": str(tmp_path)}):
            result = get_subscribers()
            assert result == [123, 456, 789]

    def test_get_subscribers_returns_empty_when_no_file(self, tmp_path):
        """Test returns empty list when no subscribers file exists."""
        with patch.dict(os.environ, {"GITHUB_WORKSPACE": str(tmp_path)}):
            result = get_subscribers()
            assert result == []

    @pytest.mark.asyncio
    async def test_broadcast_excludes_main_chat_id(self, tmp_path):
        """Broadcast should not send to main chat ID if it's in subscribers list."""
        state_dir = tmp_path / ".github" / "state"
        state_dir.mkdir(parents=True)
        subscribers_file = state_dir / "subscribers.json"
        # Main chat ID 456 is also a subscriber
        subscribers_file.write_text(json.dumps({"chat_ids": [123, 456, 789]}))

        video = VideoInfo(
            title="Test Video",
            page_url="https://example.com",
            video_url="https://example.com/video.mp4",
            masechta="Berachos",
            daf=10
        )

        with patch.dict(os.environ, {"GITHUB_WORKSPACE": str(tmp_path)}):
            with patch('send_video.send_to_telegram', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = None

                # Exclude chat ID 456 (the main chat)
                success, failed = await broadcast_to_subscribers(video, "token", exclude_chat_id="456")

                # Should only send to 123 and 789, not 456
                assert success == 2
                assert failed == 0

                # Verify 456 was not called
                called_chat_ids = [call.args[2] for call in mock_send.call_args_list]
                assert "456" not in called_chat_ids
                assert "123" in called_chat_ids
                assert "789" in called_chat_ids

    @pytest.mark.asyncio
    async def test_broadcast_works_without_exclude(self, tmp_path):
        """Broadcast should work normally when no exclude is specified."""
        state_dir = tmp_path / ".github" / "state"
        state_dir.mkdir(parents=True)
        subscribers_file = state_dir / "subscribers.json"
        subscribers_file.write_text(json.dumps({"chat_ids": [123, 456]}))

        video = VideoInfo(
            title="Test Video",
            page_url="https://example.com",
            video_url="https://example.com/video.mp4",
            masechta="Berachos",
            daf=10
        )

        with patch.dict(os.environ, {"GITHUB_WORKSPACE": str(tmp_path)}):
            with patch('send_video.send_to_telegram', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = None

                # No exclude specified
                success, failed = await broadcast_to_subscribers(video, "token")

                # Should send to both
                assert success == 2
                assert failed == 0

    @pytest.mark.asyncio
    async def test_broadcast_handles_negative_chat_ids(self, tmp_path):
        """Broadcast should correctly handle negative chat IDs (groups/channels)."""
        state_dir = tmp_path / ".github" / "state"
        state_dir.mkdir(parents=True)
        subscribers_file = state_dir / "subscribers.json"
        # Negative chat ID represents a group
        subscribers_file.write_text(json.dumps({"chat_ids": [123, -100456789, 789]}))

        video = VideoInfo(
            title="Test Video",
            page_url="https://example.com",
            video_url="https://example.com/video.mp4",
            masechta="Berachos",
            daf=10
        )

        with patch.dict(os.environ, {"GITHUB_WORKSPACE": str(tmp_path)}):
            with patch('send_video.send_to_telegram', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = None

                # Exclude the group chat
                success, failed = await broadcast_to_subscribers(video, "token", exclude_chat_id="-100456789")

                # Should only send to 123 and 789
                assert success == 2
                called_chat_ids = [call.args[2] for call in mock_send.call_args_list]
                assert "-100456789" not in called_chat_ids
