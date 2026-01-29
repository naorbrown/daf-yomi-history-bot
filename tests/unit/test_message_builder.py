"""
Unit tests for message_builder module.

Tests cover:
- Welcome message formatting
- Help message formatting
- Video caption building
- Error messages
- Rate limited messages
- Content validation
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.message_builder import MessageBuilder, VideoInfo


class TestMessageBuilder:
    """Tests for MessageBuilder class."""

    def test_welcome_message_contains_commands(self):
        """Test welcome message lists all commands."""
        msg = MessageBuilder.build_welcome()
        assert "/today" in msg
        assert "/help" in msg

    def test_welcome_message_contains_schedule(self):
        """Test welcome message mentions schedule."""
        msg = MessageBuilder.build_welcome()
        assert "6:00 AM Israel time" in msg

    def test_welcome_message_mentions_alldaf(self):
        """Test welcome message mentions AllDaf.org."""
        msg = MessageBuilder.build_welcome()
        assert "AllDaf.org" in msg

    def test_welcome_message_mentions_abramson(self):
        """Test welcome message mentions Dr. Henry Abramson."""
        msg = MessageBuilder.build_welcome()
        assert "Henry Abramson" in msg

    def test_help_message_contains_commands(self):
        """Test help message lists all commands."""
        msg = MessageBuilder.build_help()
        assert "/today" in msg
        assert "/help" in msg

    def test_help_message_contains_schedule(self):
        """Test help message mentions schedule."""
        msg = MessageBuilder.build_help()
        assert "6:00 AM Israel time" in msg

    def test_help_message_contains_about(self):
        """Test help message has about section."""
        msg = MessageBuilder.build_help()
        assert "About" in msg

    def test_error_message_contains_alldaf_link(self):
        """Test error message provides AllDaf.org link."""
        msg = MessageBuilder.build_error()
        assert "alldaf.org" in msg.lower()

    def test_error_message_is_helpful(self):
        """Test error message is helpful."""
        msg = MessageBuilder.build_error()
        assert "try again" in msg.lower() or "visit" in msg.lower()

    def test_loading_message_not_empty(self):
        """Test loading message is not empty."""
        msg = MessageBuilder.build_loading()
        assert len(msg) > 0

    def test_rate_limited_message_default(self):
        """Test rate limited message without time."""
        msg = MessageBuilder.build_rate_limited()
        assert "too many" in msg.lower() or "wait" in msg.lower()

    def test_rate_limited_message_with_seconds(self):
        """Test rate limited message with specific time."""
        msg = MessageBuilder.build_rate_limited(seconds_remaining=30)
        assert "30" in msg
        assert "seconds" in msg.lower()

    def test_rate_limited_message_zero_seconds(self):
        """Test rate limited message with 0 seconds."""
        msg = MessageBuilder.build_rate_limited(seconds_remaining=0)
        # Should use default message without specific time
        assert "too many" in msg.lower() or "wait" in msg.lower()


class TestVideoCaptions:
    """Tests for video caption building."""

    @pytest.fixture
    def sample_video(self):
        """Create a sample VideoInfo for testing."""
        return VideoInfo(
            title="Menachos 17 - The Temple Service",
            page_url="https://alldaf.org/p/12345",
            video_url="https://cdn.jwplayer.com/videos/abc123.mp4",
            masechta="Menachos",
            daf=17,
        )

    def test_video_caption_contains_masechta(self, sample_video):
        """Test caption contains masechta name."""
        caption = MessageBuilder.build_video_caption(sample_video)
        assert "Menachos" in caption

    def test_video_caption_contains_daf(self, sample_video):
        """Test caption contains daf number."""
        caption = MessageBuilder.build_video_caption(sample_video)
        assert "17" in caption

    def test_video_caption_contains_title(self, sample_video):
        """Test caption contains video title."""
        caption = MessageBuilder.build_video_caption(sample_video)
        assert "Temple Service" in caption

    def test_video_caption_contains_page_url(self, sample_video):
        """Test caption contains page URL."""
        caption = MessageBuilder.build_video_caption(sample_video)
        assert sample_video.page_url in caption

    def test_video_text_same_as_caption(self, sample_video):
        """Test video text is same as caption."""
        caption = MessageBuilder.build_video_caption(sample_video)
        text = MessageBuilder.build_video_text(sample_video)
        assert caption == text

    def test_daily_broadcast_contains_greeting(self, sample_video):
        """Test daily broadcast has greeting."""
        msg = MessageBuilder.build_daily_broadcast(sample_video)
        assert "morning" in msg.lower() or "today" in msg.lower()

    def test_daily_broadcast_contains_video_info(self, sample_video):
        """Test daily broadcast contains video info."""
        msg = MessageBuilder.build_daily_broadcast(sample_video)
        assert "Menachos" in msg
        assert "17" in msg


class TestVideoInfo:
    """Tests for VideoInfo dataclass."""

    def test_video_info_creation(self):
        """Test VideoInfo can be created with all fields."""
        video = VideoInfo(
            title="Test Title",
            page_url="https://example.com/page",
            video_url="https://example.com/video.mp4",
            masechta="Berachos",
            daf=10,
        )
        assert video.title == "Test Title"
        assert video.page_url == "https://example.com/page"
        assert video.video_url == "https://example.com/video.mp4"
        assert video.masechta == "Berachos"
        assert video.daf == 10

    def test_video_info_with_none_video_url(self):
        """Test VideoInfo can have None video_url."""
        video = VideoInfo(
            title="Test Title",
            page_url="https://example.com/page",
            video_url=None,
            masechta="Berachos",
            daf=10,
        )
        assert video.video_url is None

    def test_video_info_special_characters_in_title(self):
        """Test VideoInfo handles special characters in title."""
        video = VideoInfo(
            title='Test\'s Title - With "Quotes" & Symbols!',
            page_url="https://example.com/page",
            video_url=None,
            masechta="Berachos",
            daf=10,
        )
        # Should be able to build caption without errors
        caption = MessageBuilder.build_video_caption(video)
        assert "Test's Title" in caption
