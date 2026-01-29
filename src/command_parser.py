"""
Command Parser for Telegram Bot Commands.

Parses and validates incoming Telegram bot commands with support for:
- Standard commands: /start, /help, /today
- Bot mention suffix: /start@DafHistoryBot
- Command parameters: /command param1 param2
- Case-insensitive matching
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class CommandResult:
    """Result of parsing a command."""

    command: Optional[str]
    params: str
    is_valid: bool
    raw_text: str

    @property
    def has_params(self) -> bool:
        """Check if command has parameters."""
        return bool(self.params.strip())


# Valid commands for this bot
VALID_COMMANDS = frozenset(["start", "help", "today"])


def parse_command(text: Optional[str]) -> CommandResult:
    """
    Parse a Telegram message text to extract command and parameters.

    Handles various input formats:
    - /start -> CommandResult(command="start", params="")
    - /start@BotName -> CommandResult(command="start", params="")
    - /today param -> CommandResult(command="today", params="param")
    - /HELP -> CommandResult(command="help", params="")  # case-insensitive
    - Regular text -> CommandResult(command=None, is_valid=False)

    Args:
        text: The message text to parse

    Returns:
        CommandResult with parsed command information
    """
    # Handle None, empty, or non-string input
    if text is None:
        return CommandResult(command=None, params="", is_valid=False, raw_text="")

    if not isinstance(text, str):
        return CommandResult(
            command=None, params="", is_valid=False, raw_text=str(text)
        )

    # Clean and normalize
    raw_text = text
    text = text.strip()

    if not text:
        return CommandResult(command=None, params="", is_valid=False, raw_text=raw_text)

    # Must start with /
    if not text.startswith("/"):
        return CommandResult(command=None, params="", is_valid=False, raw_text=raw_text)

    # Split into parts
    parts = text.split(None, 1)  # Split on first whitespace
    command_part = parts[0][1:]  # Remove leading /
    params = parts[1].strip() if len(parts) > 1 else ""

    # Handle @botname suffix (e.g., /start@DafHistoryBot)
    if "@" in command_part:
        command_part = command_part.split("@")[0]

    # Normalize to lowercase
    command = command_part.lower()

    # Validate command
    is_valid = command in VALID_COMMANDS

    return CommandResult(
        command=command if is_valid else None,
        params=params,
        is_valid=is_valid,
        raw_text=raw_text,
    )


def is_command(text: Optional[str]) -> bool:
    """Check if text is a valid bot command."""
    return parse_command(text).is_valid


def get_command(text: Optional[str]) -> Optional[str]:
    """Extract command name from text, or None if not a valid command."""
    return parse_command(text).command
