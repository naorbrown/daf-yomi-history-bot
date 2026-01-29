"""
Message Builder for Telegram Bot Messages.

Builds formatted messages for the bot with consistent styling.
Uses plain text to avoid Markdown parsing issues.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class VideoInfo:
    """Information about a video."""

    title: str
    page_url: str
    video_url: Optional[str]
    masechta: str
    daf: int


class MessageBuilder:
    """
    Build formatted messages for the Telegram bot.

    All messages use plain text (no Markdown) to avoid parsing issues
    with special characters in titles.
    """

    # Bot messages
    WELCOME_MESSAGE = (
        "Welcome to Daf Yomi History Bot!\n\n"
        "I send you daily Jewish History videos from Dr. Henry Abramson's series "
        "on AllDaf.org, matching the Daf Yomi schedule.\n\n"
        "Commands:\n"
        "/today - Get today's video now\n"
        "/help - Show this message\n\n"
        "You'll automatically receive the daily video every morning at "
        "6:00 AM Israel time.\n\n"
        "Enjoy your learning!"
    )

    HELP_MESSAGE = (
        "Daf Yomi History Bot - Help\n\n"
        "Available Commands:\n\n"
        "/today - Get today's Daf Yomi history video\n"
        "/help - Show this help message\n\n"
        "About:\n"
        "This bot sends Jewish History videos from AllDaf.org's series "
        "by Dr. Henry Abramson. Each video corresponds to the daily Daf Yomi page.\n\n"
        "Schedule:\n"
        "Daily videos are sent automatically at 6:00 AM Israel time."
    )

    ERROR_MESSAGE = (
        "Sorry, I couldn't find today's video. Please try again later.\n\n"
        "You can also visit AllDaf.org directly:\n"
        "https://alldaf.org/series/3940"
    )

    RATE_LIMITED_MESSAGE = (
        "You're sending too many requests. Please wait a moment before trying again."
    )

    LOADING_MESSAGE = "Finding today's Daf Yomi history video..."

    @classmethod
    def build_welcome(cls) -> str:
        """Build welcome message."""
        return cls.WELCOME_MESSAGE

    @classmethod
    def build_help(cls) -> str:
        """Build help message."""
        return cls.HELP_MESSAGE

    @classmethod
    def build_error(cls) -> str:
        """Build error message."""
        return cls.ERROR_MESSAGE

    @classmethod
    def build_rate_limited(cls, seconds_remaining: float = 0) -> str:
        """Build rate limited message."""
        if seconds_remaining > 0:
            return (
                f"You're sending too many requests. "
                f"Please wait {int(seconds_remaining)} seconds before trying again."
            )
        return cls.RATE_LIMITED_MESSAGE

    @classmethod
    def build_loading(cls) -> str:
        """Build loading message."""
        return cls.LOADING_MESSAGE

    @classmethod
    def build_video_caption(cls, video: VideoInfo) -> str:
        """
        Build caption for a video message.

        Args:
            video: VideoInfo with video details

        Returns:
            Formatted caption string (plain text)
        """
        return (
            f"Today's Daf Yomi History\n\n"
            f"{video.masechta} {video.daf}\n"
            f"{video.title}\n\n"
            f"View on AllDaf.org: {video.page_url}"
        )

    @classmethod
    def build_video_text(cls, video: VideoInfo) -> str:
        """
        Build text message when video URL is not available.

        Args:
            video: VideoInfo with video details

        Returns:
            Formatted text string
        """
        return cls.build_video_caption(video)

    @classmethod
    def build_daily_broadcast(cls, video: VideoInfo) -> str:
        """
        Build message for daily broadcast.

        Args:
            video: VideoInfo with video details

        Returns:
            Formatted broadcast message
        """
        return (
            f"Good morning! Here's today's Daf Yomi History video:\n\n"
            f"{video.masechta} {video.daf}\n"
            f"{video.title}\n\n"
            f"View on AllDaf.org: {video.page_url}"
        )
