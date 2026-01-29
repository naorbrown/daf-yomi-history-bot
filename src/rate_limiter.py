"""
Rate Limiter for Telegram Bot Commands.

Prevents abuse by limiting how many requests a user can make
within a time window. Like nachyomi-bot, defaults to 5 requests
per 60-second window per user.
"""

import time
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class UserRateInfo:
    """Rate limiting info for a single user."""

    requests: int = 0
    window_start: float = 0.0


@dataclass
class RateLimiter:
    """
    Rate limiter with per-user tracking.

    Args:
        max_requests: Maximum requests allowed per window (default: 5)
        window_seconds: Time window in seconds (default: 60)
        max_entries: Maximum users to track before cleanup (default: 10000)
    """

    max_requests: int = 5
    window_seconds: int = 60
    max_entries: int = 10000
    _users: Dict[int, UserRateInfo] = field(default_factory=dict)

    def is_allowed(self, user_id: int) -> bool:
        """
        Check if a request from user_id is allowed.

        Args:
            user_id: Telegram user ID

        Returns:
            True if request is allowed, False if rate limited
        """
        now = time.time()

        # Cleanup if too many entries
        if len(self._users) >= self.max_entries:
            self._cleanup(now)

        # Get or create user info
        if user_id not in self._users:
            self._users[user_id] = UserRateInfo(requests=1, window_start=now)
            return True

        user = self._users[user_id]

        # Check if window has expired
        if now - user.window_start >= self.window_seconds:
            # Reset window
            user.requests = 1
            user.window_start = now
            return True

        # Check if within limits
        if user.requests < self.max_requests:
            user.requests += 1
            return True

        # Rate limited
        return False

    def get_remaining(self, user_id: int) -> int:
        """
        Get remaining requests for a user in current window.

        Args:
            user_id: Telegram user ID

        Returns:
            Number of remaining requests (0 if rate limited)
        """
        now = time.time()

        if user_id not in self._users:
            return self.max_requests

        user = self._users[user_id]

        # Window expired
        if now - user.window_start >= self.window_seconds:
            return self.max_requests

        return max(0, self.max_requests - user.requests)

    def get_reset_time(self, user_id: int) -> float:
        """
        Get seconds until rate limit resets for a user.

        Args:
            user_id: Telegram user ID

        Returns:
            Seconds until reset (0 if not rate limited)
        """
        now = time.time()

        if user_id not in self._users:
            return 0.0

        user = self._users[user_id]
        elapsed = now - user.window_start

        if elapsed >= self.window_seconds:
            return 0.0

        return self.window_seconds - elapsed

    def reset(self, user_id: int = None) -> None:
        """
        Reset rate limits.

        Args:
            user_id: Specific user to reset, or None to reset all
        """
        if user_id is not None:
            self._users.pop(user_id, None)
        else:
            self._users.clear()

    def _cleanup(self, now: float) -> None:
        """Remove expired entries to prevent memory growth."""
        expired_users = [
            uid
            for uid, info in self._users.items()
            if now - info.window_start >= self.window_seconds
        ]
        for uid in expired_users:
            del self._users[uid]


# Global rate limiter instance (5 requests per minute per user)
default_limiter = RateLimiter()


def check_rate_limit(user_id: int) -> bool:
    """
    Check if a user is within rate limits using default limiter.

    Args:
        user_id: Telegram user ID

    Returns:
        True if allowed, False if rate limited
    """
    return default_limiter.is_allowed(user_id)
