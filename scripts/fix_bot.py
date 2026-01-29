#!/usr/bin/env python3
"""
Diagnostic and fix script for Daf Yomi History Bot.

Run this script to:
1. Check if a webhook is blocking polling
2. Delete the webhook if present
3. Verify the state file is valid
4. Test that getUpdates works

Usage:
    TELEGRAM_BOT_TOKEN=your_token python scripts/fix_bot.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

TELEGRAM_API_BASE = "https://api.telegram.org/bot"
REQUEST_TIMEOUT = 30.0


def get_repo_root() -> Path:
    """Get the repository root directory."""
    workspace = os.environ.get("GITHUB_WORKSPACE")
    if workspace:
        return Path(workspace)
    return Path(__file__).parent.parent


REPO_ROOT = get_repo_root()
STATE_FILE = REPO_ROOT / ".github" / "state" / "last_update_id.json"


async def check_webhook(token: str) -> dict:
    """Check current webhook status."""
    print("\n[1/4] Checking webhook status...")

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.get(f"{TELEGRAM_API_BASE}{token}/getWebhookInfo")
        response.raise_for_status()
        data = response.json()

        if not data.get("ok"):
            print(f"  ERROR: API returned error: {data}")
            return {}

        result = data.get("result", {})
        webhook_url = result.get("url", "")
        pending_count = result.get("pending_update_count", 0)

        if webhook_url:
            print(f"  WARNING: Webhook is SET!")
            print(f"  Webhook URL: {webhook_url}")
            print(f"  Pending updates: {pending_count}")
            print(f"  This is BLOCKING polling (getUpdates)!")
        else:
            print(f"  OK: No webhook is set")
            print(f"  Pending updates: {pending_count}")

        return result


async def delete_webhook(token: str) -> bool:
    """Delete existing webhook."""
    print("\n[2/4] Deleting webhook...")

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(
            f"{TELEGRAM_API_BASE}{token}/deleteWebhook",
            json={"drop_pending_updates": False}
        )
        response.raise_for_status()
        data = response.json()

        if data.get("ok"):
            print("  OK: Webhook deleted successfully")
            return True
        else:
            print(f"  ERROR: Failed to delete webhook: {data}")
            return False


def check_state_file() -> bool:
    """Check if state file is valid."""
    print("\n[3/4] Checking state file...")
    print(f"  State file path: {STATE_FILE}")

    if not STATE_FILE.exists():
        print("  WARNING: State file does not exist")
        print("  This means the bot will start fresh and process all pending updates")
        return False

    try:
        data = json.loads(STATE_FILE.read_text())
        last_update_id = data.get("last_update_id")

        if last_update_id is None:
            print("  WARNING: State file exists but last_update_id is null")
            return False

        if not isinstance(last_update_id, int):
            print(f"  WARNING: last_update_id is not an integer: {last_update_id}")
            return False

        print(f"  OK: State file is valid")
        print(f"  Last update ID: {last_update_id}")
        return True

    except json.JSONDecodeError as e:
        print(f"  ERROR: State file is not valid JSON: {e}")
        return False


async def test_get_updates(token: str) -> bool:
    """Test that getUpdates works."""
    print("\n[4/4] Testing getUpdates...")

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        # Use a high offset to just test connectivity (don't fetch real updates)
        response = await client.post(
            f"{TELEGRAM_API_BASE}{token}/getUpdates",
            data={"timeout": 0, "limit": 1, "offset": 999999999}
        )

        if response.status_code == 409:
            print("  ERROR: getUpdates returned 409 Conflict")
            print("  This means a webhook is still blocking polling!")
            return False

        response.raise_for_status()
        data = response.json()

        if data.get("ok"):
            print("  OK: getUpdates is working")
            return True
        else:
            print(f"  ERROR: getUpdates failed: {data}")
            return False


async def main() -> int:
    """Main entry point."""
    print("=" * 60)
    print("Daf Yomi History Bot - Diagnostic & Fix Script")
    print("=" * 60)

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("\nERROR: TELEGRAM_BOT_TOKEN environment variable not set!")
        print("Usage: TELEGRAM_BOT_TOKEN=your_token python scripts/fix_bot.py")
        return 1

    print(f"\nToken is set (length: {len(token)})")

    # Step 1: Check webhook status
    webhook_info = await check_webhook(token)
    webhook_was_set = bool(webhook_info.get("url"))

    # Step 2: Delete webhook (always do this to be safe)
    webhook_deleted = await delete_webhook(token)

    # Step 3: Check state file
    state_valid = check_state_file()

    # Step 4: Test getUpdates
    updates_working = await test_get_updates(token)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    issues_found = []
    issues_fixed = []

    if webhook_was_set:
        if webhook_deleted:
            issues_fixed.append("Webhook was blocking polling - FIXED")
        else:
            issues_found.append("Webhook is blocking polling - FAILED TO FIX")

    if not state_valid:
        issues_found.append("State file is missing or invalid (will be recreated on next run)")

    if not updates_working:
        issues_found.append("getUpdates is not working")

    if issues_fixed:
        print("\nIssues FIXED:")
        for issue in issues_fixed:
            print(f"  ✓ {issue}")

    if issues_found:
        print("\nIssues remaining:")
        for issue in issues_found:
            print(f"  ✗ {issue}")
        return 1

    if not issues_fixed and not issues_found:
        print("\n✓ All checks passed! Bot should be working correctly.")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
