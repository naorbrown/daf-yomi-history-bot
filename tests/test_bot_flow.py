#!/usr/bin/env python3
"""
Test script to verify the bot flow matches nachyomi-bot pattern.
This simulates the complete polling flow without needing real Telegram credentials.
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Simulate the key parts of poll_commands.py


class MockStateManager:
    """Simulates StateManager with a temp file."""

    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def get_last_update_id(self):
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text())
                return data.get("last_update_id")
            except (json.JSONDecodeError, KeyError):
                return None
        return None

    def set_last_update_id(self, update_id: int):
        self.state_file.write_text(json.dumps({"last_update_id": update_id}, indent=2))


def process_updates_nachyomi_style(state: MockStateManager, updates: list) -> tuple:
    """
    Process updates exactly like nachyomi-bot.
    Returns (processed_count, final_last_update_id)
    """
    # Load last update ID, default to 0 (nachyomi-bot pattern)
    last_update_id = state.get_last_update_id()
    if last_update_id is None:
        last_update_id = 0
        print(f"No state file found, defaulting to 0")

    # Always use offset = lastUpdateId + 1
    offset = last_update_id + 1
    print(f"Would fetch updates with offset={offset}")

    # Simulate receiving updates
    if not updates:
        print("No new updates")
        # nachyomi-bot exits without saving state when no updates
        return 0, last_update_id

    print(f"Received {len(updates)} update(s)")
    processed = 0

    for update in updates:
        # Track highest update_id (nachyomi-bot does this FIRST)
        update_id = update.get("update_id")
        last_update_id = max(last_update_id, update_id) if update_id else last_update_id

        message = update.get("message", {})
        text = message.get("text")
        chat_id = message.get("chat", {}).get("id")

        if not message or not text:
            print(f"  Update {update_id}: no message/text, skipping")
            continue

        if text.startswith("/"):
            command = text.split()[0].split("@")[0][1:].lower()
            print(f"  Update {update_id}: processing /{command} for chat {chat_id}")
            processed += 1
        else:
            print(f"  Update {update_id}: not a command, skipping")

    # Save state for next run (nachyomi-bot always saves if we got updates)
    state.set_last_update_id(last_update_id)
    print(f"Saved last_update_id={last_update_id}")

    return processed, last_update_id


def run_scenario(name: str, initial_state: dict | None, updates: list, expected_offset: int, expected_final_id: int):
    """Run a test scenario."""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")

    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"

        # Set up initial state
        if initial_state is not None:
            state_file.write_text(json.dumps(initial_state, indent=2))
            print(f"Initial state: {initial_state}")
        else:
            print("Initial state: None (first run)")

        state = MockStateManager(state_file)

        # Get the offset that would be used
        last_id = state.get_last_update_id()
        if last_id is None:
            last_id = 0
        actual_offset = last_id + 1

        print(f"Expected offset: {expected_offset}, Actual offset: {actual_offset}")
        assert actual_offset == expected_offset, f"Offset mismatch! Expected {expected_offset}, got {actual_offset}"

        # Process updates
        processed, final_id = process_updates_nachyomi_style(state, updates)

        print(f"Expected final_id: {expected_final_id}, Actual final_id: {final_id}")
        assert final_id == expected_final_id, f"Final ID mismatch! Expected {expected_final_id}, got {final_id}"

        # Verify state file
        if updates:
            saved_state = json.loads(state_file.read_text())
            print(f"Saved state: {saved_state}")
            assert saved_state["last_update_id"] == expected_final_id

        print(f"PASS")
        return True


def main():
    print("Testing bot flow against nachyomi-bot pattern")

    # Test 1: First run (no state file), with pending commands
    run_scenario(
        name="First run with pending commands",
        initial_state=None,
        updates=[
            {"update_id": 100, "message": {"text": "/start", "chat": {"id": 123}, "from": {"id": 456}}},
            {"update_id": 101, "message": {"text": "/help", "chat": {"id": 123}, "from": {"id": 456}}},
        ],
        expected_offset=1,  # 0 + 1 = 1
        expected_final_id=101,
    )

    # Test 2: First run (no state file), no pending commands
    run_scenario(
        name="First run with no pending commands",
        initial_state=None,
        updates=[],
        expected_offset=1,  # 0 + 1 = 1
        expected_final_id=0,  # Unchanged when no updates
    )

    # Test 3: Subsequent run with existing state
    run_scenario(
        name="Subsequent run with new command",
        initial_state={"last_update_id": 100},
        updates=[
            {"update_id": 101, "message": {"text": "/today", "chat": {"id": 789}, "from": {"id": 111}}},
        ],
        expected_offset=101,  # 100 + 1 = 101
        expected_final_id=101,
    )

    # Test 4: Subsequent run with no new updates
    run_scenario(
        name="Subsequent run with no new updates",
        initial_state={"last_update_id": 100},
        updates=[],
        expected_offset=101,  # 100 + 1 = 101
        expected_final_id=100,  # Unchanged when no updates
    )

    # Test 5: State file has last_update_id = 0
    run_scenario(
        name="State file with last_update_id = 0",
        initial_state={"last_update_id": 0},
        updates=[
            {"update_id": 50, "message": {"text": "/start", "chat": {"id": 123}, "from": {"id": 456}}},
        ],
        expected_offset=1,  # 0 + 1 = 1
        expected_final_id=50,
    )

    # Test 6: Mixed updates (some with commands, some without)
    run_scenario(
        name="Mixed updates with and without commands",
        initial_state={"last_update_id": 200},
        updates=[
            {"update_id": 201, "message": {"text": "hello", "chat": {"id": 123}, "from": {"id": 456}}},  # Not a command
            {"update_id": 202, "message": {"text": "/help", "chat": {"id": 789}, "from": {"id": 111}}},  # Command
            {"update_id": 203},  # No message at all
        ],
        expected_offset=201,  # 200 + 1 = 201
        expected_final_id=203,  # Should track ALL update_ids, even non-commands
    )

    # Test 7: Verify offset=1 fetches all recent updates
    run_scenario(
        name="First run should process updates with high IDs",
        initial_state=None,
        updates=[
            # Simulate Telegram returning updates with high IDs (like it would for a bot that just started)
            {"update_id": 999999, "message": {"text": "/start", "chat": {"id": 123}, "from": {"id": 456}}},
        ],
        expected_offset=1,  # First run always uses offset=1
        expected_final_id=999999,
    )

    print(f"\n{'='*60}")
    print("ALL TESTS PASSED!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
