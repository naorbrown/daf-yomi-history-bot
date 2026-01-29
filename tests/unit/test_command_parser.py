"""
Unit tests for command_parser module.

Tests cover:
- Valid command parsing
- Bot mention handling (@DafHistoryBot suffix)
- Parameter extraction
- Case-insensitive matching
- Invalid input handling
- Edge cases
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.command_parser import parse_command, is_command, get_command, CommandResult


class TestParseCommand:
    """Tests for parse_command function."""

    def test_parse_start_command(self):
        """Test parsing /start command."""
        result = parse_command("/start")
        assert result.command == "start"
        assert result.params == ""
        assert result.is_valid is True

    def test_parse_help_command(self):
        """Test parsing /help command."""
        result = parse_command("/help")
        assert result.command == "help"
        assert result.params == ""
        assert result.is_valid is True

    def test_parse_today_command(self):
        """Test parsing /today command."""
        result = parse_command("/today")
        assert result.command == "today"
        assert result.params == ""
        assert result.is_valid is True

    def test_parse_command_with_bot_mention(self):
        """Test stripping @botname suffix."""
        result = parse_command("/start@DafHistoryBot")
        assert result.command == "start"
        assert result.params == ""
        assert result.is_valid is True

    def test_parse_command_with_params(self):
        """Test extracting parameters."""
        result = parse_command("/today some params")
        assert result.command == "today"
        assert result.params == "some params"
        assert result.is_valid is True
        assert result.has_params is True

    def test_parse_command_case_insensitive(self):
        """Test case-insensitive command matching."""
        result = parse_command("/HELP")
        assert result.command == "help"
        assert result.is_valid is True

        result = parse_command("/Today")
        assert result.command == "today"
        assert result.is_valid is True

        result = parse_command("/START")
        assert result.command == "start"
        assert result.is_valid is True

    def test_parse_invalid_command(self):
        """Test handling unknown commands."""
        result = parse_command("/unknown")
        assert result.command is None
        assert result.is_valid is False

    def test_parse_non_command_text(self):
        """Test handling regular text (not a command)."""
        result = parse_command("hello world")
        assert result.command is None
        assert result.is_valid is False

    def test_parse_empty_string(self):
        """Test handling empty string."""
        result = parse_command("")
        assert result.command is None
        assert result.is_valid is False

    def test_parse_none(self):
        """Test handling None input."""
        result = parse_command(None)
        assert result.command is None
        assert result.is_valid is False

    def test_parse_whitespace_only(self):
        """Test handling whitespace-only input."""
        result = parse_command("   ")
        assert result.command is None
        assert result.is_valid is False

    def test_parse_leading_whitespace(self):
        """Test handling leading whitespace."""
        result = parse_command("  /start")
        assert result.command == "start"
        assert result.is_valid is True

    def test_parse_trailing_whitespace(self):
        """Test handling trailing whitespace."""
        result = parse_command("/start  ")
        assert result.command == "start"
        assert result.params == ""
        assert result.is_valid is True

    def test_parse_multiple_spaces_in_params(self):
        """Test handling multiple spaces in parameters."""
        result = parse_command("/today param1   param2")
        assert result.command == "today"
        assert result.params == "param1   param2"

    def test_parse_command_with_newline(self):
        """Test handling command with newline in params."""
        result = parse_command("/today line1\nline2")
        assert result.command == "today"
        assert result.params == "line1\nline2"

    def test_parse_slash_only(self):
        """Test handling just a slash."""
        result = parse_command("/")
        assert result.command is None
        assert result.is_valid is False

    def test_parse_non_string_input(self):
        """Test handling non-string input."""
        result = parse_command(123)
        assert result.command is None
        assert result.is_valid is False

    def test_raw_text_preserved(self):
        """Test that raw_text is preserved."""
        result = parse_command("  /start  ")
        assert result.raw_text == "  /start  "


class TestIsCommand:
    """Tests for is_command function."""

    def test_valid_commands(self):
        """Test is_command returns True for valid commands."""
        assert is_command("/start") is True
        assert is_command("/help") is True
        assert is_command("/today") is True

    def test_invalid_inputs(self):
        """Test is_command returns False for invalid inputs."""
        assert is_command("hello") is False
        assert is_command("/unknown") is False
        assert is_command("") is False
        assert is_command(None) is False


class TestGetCommand:
    """Tests for get_command function."""

    def test_get_valid_commands(self):
        """Test get_command extracts command names."""
        assert get_command("/start") == "start"
        assert get_command("/help") == "help"
        assert get_command("/today") == "today"

    def test_get_invalid_returns_none(self):
        """Test get_command returns None for invalid inputs."""
        assert get_command("hello") is None
        assert get_command("/unknown") is None
        assert get_command("") is None
        assert get_command(None) is None


class TestCommandResult:
    """Tests for CommandResult dataclass."""

    def test_has_params_true(self):
        """Test has_params property when params exist."""
        result = CommandResult(
            command="today", params="test param", is_valid=True, raw_text="/today test param"
        )
        assert result.has_params is True

    def test_has_params_false(self):
        """Test has_params property when no params."""
        result = CommandResult(command="start", params="", is_valid=True, raw_text="/start")
        assert result.has_params is False

    def test_has_params_whitespace_only(self):
        """Test has_params with whitespace-only params."""
        result = CommandResult(command="today", params="   ", is_valid=True, raw_text="/today   ")
        assert result.has_params is False
