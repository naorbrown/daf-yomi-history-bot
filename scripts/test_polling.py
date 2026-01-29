#!/usr/bin/env python3
"""
Test script to verify the polling logic works correctly.
Run with: TELEGRAM_BOT_TOKEN=test python scripts/test_polling.py

This simulates the bot receiving and processing commands.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))

from poll_commands import (
    TelegramAPI,
    StateManager,
    process_updates,
    main,
)


async def test_with_mock_telegram():
    """Test the full polling flow with mocked Telegram API."""
    print("=" * 60)
    print("Testing poll_commands.py with mocked Telegram API")
    print("=" * 60)

    # Create temp state directory
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        state_dir = Path(tmpdir)
        state_file = state_dir / "last_update_id.json"
        rate_file = state_dir / "rate_limits.json"

        with patch("poll_commands.STATE_DIR", state_dir):
            with patch("poll_commands.STATE_FILE", state_file):
                with patch("poll_commands.RATE_LIMIT_FILE", rate_file):

                    # Test 1: First run with pending commands
                    print("\n[TEST 1] First run with pending /start command")
                    print("-" * 40)

                    state = StateManager()
                    api = AsyncMock(spec=TelegramAPI)

                    # Simulate Telegram returning a /start command
                    api.get_updates.return_value = [
                        {
                            "update_id": 12345,
                            "message": {
                                "text": "/start",
                                "chat": {"id": 999},
                                "from": {"id": 888, "first_name": "Test"},
                            },
                        }
                    ]
                    api.send_message.return_value = {"ok": True}

                    processed = await process_updates(api, state)

                    print(f"  - Updates processed: {processed}")
                    print(f"  - get_updates called with offset: {api.get_updates.call_args}")
                    print(f"  - send_message called: {api.send_message.called}")
                    print(f"  - State file exists: {state_file.exists()}")

                    if state_file.exists():
                        saved = json.loads(state_file.read_text())
                        print(f"  - Saved state: {saved}")

                    # Verify
                    assert processed == 1, f"Expected 1 processed, got {processed}"
                    assert api.get_updates.call_args[0][0] == 1, "First run should use offset=1"
                    assert api.send_message.called, "Should have sent welcome message"
                    assert state_file.exists(), "State file should be created"
                    print("  ✓ PASSED")

                    # Test 2: Subsequent run with /today command
                    print("\n[TEST 2] Subsequent run with /today command")
                    print("-" * 40)

                    api.reset_mock()
                    api.get_updates.return_value = [
                        {
                            "update_id": 12346,
                            "message": {
                                "text": "/today",
                                "chat": {"id": 999},
                                "from": {"id": 888},
                            },
                        }
                    ]
                    api.send_message.return_value = {"ok": True}
                    api.send_video.return_value = {"ok": True}

                    # Mock the video fetching
                    with patch("poll_commands.get_todays_daf") as mock_daf:
                        with patch("poll_commands.get_jewish_history_video") as mock_video:
                            from poll_commands import DafInfo, VideoInfo
                            mock_daf.return_value = DafInfo(masechta="Berachos", daf=2)
                            mock_video.return_value = VideoInfo(
                                title="Test Video",
                                page_url="https://alldaf.org/test",
                                video_url="https://example.com/video.mp4",
                                masechta="Berachos",
                                daf=2,
                            )

                            state2 = StateManager()
                            processed = await process_updates(api, state2)

                    print(f"  - Updates processed: {processed}")
                    print(f"  - get_updates offset: {api.get_updates.call_args[0][0]}")
                    print(f"  - send_video called: {api.send_video.called}")

                    saved = json.loads(state_file.read_text())
                    print(f"  - Saved state: {saved}")

                    assert processed == 1, f"Expected 1 processed, got {processed}"
                    assert api.get_updates.call_args[0][0] == 12346, "Should use offset = last_id + 1"
                    print("  ✓ PASSED")

                    # Test 3: Run with no new updates
                    print("\n[TEST 3] Run with no new updates")
                    print("-" * 40)

                    api.reset_mock()
                    api.get_updates.return_value = []

                    state3 = StateManager()
                    processed = await process_updates(api, state3)

                    print(f"  - Updates processed: {processed}")
                    print(f"  - get_updates offset: {api.get_updates.call_args[0][0]}")
                    print(f"  - send_message called: {api.send_message.called}")

                    assert processed == 0, f"Expected 0 processed, got {processed}"
                    assert not api.send_message.called, "Should not send any message"
                    print("  ✓ PASSED")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
    print("\nThe polling logic is working correctly.")
    print("If Telegram commands aren't working, check:")
    print("1. GitHub Actions > Poll Bot Commands workflow is enabled")
    print("2. TELEGRAM_BOT_TOKEN secret is set in repository settings")
    print("3. Check workflow run logs for errors")


if __name__ == "__main__":
    asyncio.run(test_with_mock_telegram())
