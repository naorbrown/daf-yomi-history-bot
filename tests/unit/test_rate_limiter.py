"""
Unit tests for rate_limiter module.

Tests cover:
- Rate limiting enforcement
- Per-user tracking
- Time window expiration
- Reset functionality
- Custom configuration
- Memory cleanup
"""

import pytest
import time
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.rate_limiter import RateLimiter, check_rate_limit, default_limiter


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_allows_first_request(self):
        """Test that first request is always allowed."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        assert limiter.is_allowed(user_id=1) is True

    def test_allows_requests_within_limit(self):
        """Test that requests within limit are allowed."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        user_id = 1

        for i in range(5):
            assert limiter.is_allowed(user_id) is True, f"Request {i + 1} should be allowed"

    def test_blocks_requests_over_limit(self):
        """Test that requests over limit are blocked."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        user_id = 1

        # Use up the limit
        for _ in range(3):
            limiter.is_allowed(user_id)

        # Next request should be blocked
        assert limiter.is_allowed(user_id) is False

    def test_per_user_isolation(self):
        """Test that rate limits are per-user."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)

        # User 1 uses their limit
        assert limiter.is_allowed(user_id=1) is True
        assert limiter.is_allowed(user_id=1) is True
        assert limiter.is_allowed(user_id=1) is False

        # User 2 should still have their full limit
        assert limiter.is_allowed(user_id=2) is True
        assert limiter.is_allowed(user_id=2) is True

    def test_window_expiration(self):
        """Test that rate limit resets after window expires."""
        limiter = RateLimiter(max_requests=2, window_seconds=1)
        user_id = 1

        # Use up the limit
        limiter.is_allowed(user_id)
        limiter.is_allowed(user_id)
        assert limiter.is_allowed(user_id) is False

        # Wait for window to expire
        time.sleep(1.1)

        # Should be allowed again
        assert limiter.is_allowed(user_id) is True

    def test_get_remaining(self):
        """Test get_remaining returns correct count."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        user_id = 1

        assert limiter.get_remaining(user_id) == 5

        limiter.is_allowed(user_id)
        assert limiter.get_remaining(user_id) == 4

        limiter.is_allowed(user_id)
        limiter.is_allowed(user_id)
        assert limiter.get_remaining(user_id) == 2

    def test_get_remaining_unknown_user(self):
        """Test get_remaining for unknown user returns max."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        assert limiter.get_remaining(user_id=9999) == 5

    def test_get_reset_time(self):
        """Test get_reset_time returns correct value."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        user_id = 1

        # Unknown user should have 0 reset time
        assert limiter.get_reset_time(user_id) == 0.0

        # After a request, should have some reset time
        limiter.is_allowed(user_id)
        reset_time = limiter.get_reset_time(user_id)
        assert 0 < reset_time <= 60

    def test_reset_specific_user(self):
        """Test resetting a specific user."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)

        # Use up limits for both users
        limiter.is_allowed(user_id=1)
        limiter.is_allowed(user_id=1)
        limiter.is_allowed(user_id=2)
        limiter.is_allowed(user_id=2)

        # Both are at limit
        assert limiter.is_allowed(user_id=1) is False
        assert limiter.is_allowed(user_id=2) is False

        # Reset only user 1
        limiter.reset(user_id=1)

        # User 1 can make requests again, user 2 still blocked
        assert limiter.is_allowed(user_id=1) is True
        assert limiter.is_allowed(user_id=2) is False

    def test_reset_all_users(self):
        """Test resetting all users."""
        limiter = RateLimiter(max_requests=1, window_seconds=60)

        # Use up limits for both users
        limiter.is_allowed(user_id=1)
        limiter.is_allowed(user_id=2)

        # Both are at limit
        assert limiter.is_allowed(user_id=1) is False
        assert limiter.is_allowed(user_id=2) is False

        # Reset all
        limiter.reset()

        # Both can make requests again
        assert limiter.is_allowed(user_id=1) is True
        assert limiter.is_allowed(user_id=2) is True

    def test_custom_configuration(self):
        """Test custom rate limit configuration."""
        limiter = RateLimiter(max_requests=10, window_seconds=120)

        user_id = 1
        for _ in range(10):
            assert limiter.is_allowed(user_id) is True

        assert limiter.is_allowed(user_id) is False

    def test_cleanup_when_max_entries_exceeded(self):
        """Test memory cleanup when max_entries is exceeded."""
        limiter = RateLimiter(max_requests=5, window_seconds=1, max_entries=3)

        # Add entries for 3 users
        for user_id in range(3):
            limiter.is_allowed(user_id)

        # Wait for windows to expire
        time.sleep(1.1)

        # Adding a 4th user should trigger cleanup
        limiter.is_allowed(user_id=100)

        # Old entries should be cleaned up
        # The internal dict should not have more than max_entries
        assert len(limiter._users) <= limiter.max_entries


class TestDefaultLimiter:
    """Tests for default_limiter and check_rate_limit function."""

    def test_check_rate_limit_function(self):
        """Test check_rate_limit convenience function."""
        # Reset the default limiter first
        default_limiter.reset()

        user_id = 99999  # Use a unique user ID for this test

        # First request should be allowed
        assert check_rate_limit(user_id) is True

    def test_default_limiter_configuration(self):
        """Test default limiter has expected configuration."""
        assert default_limiter.max_requests == 5
        assert default_limiter.window_seconds == 60
