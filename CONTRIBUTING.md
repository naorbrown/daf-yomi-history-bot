# Contributing to Daf Yomi History Bot

Thank you for your interest in contributing! This document provides guidelines and information for contributors.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment. Please be kind and constructive in all interactions.

## How to Contribute

### Reporting Bugs

1. **Check existing issues** — Your bug may already be reported
2. **Create a new issue** with:
   - Clear, descriptive title
   - Steps to reproduce
   - Expected vs actual behavior
   - Relevant logs (from GitHub Actions)
   - Masechta and daf number (if applicable)

### Suggesting Features

1. **Open an issue** describing:
   - The problem you're trying to solve
   - Your proposed solution
   - Any alternatives you've considered

### Submitting Changes

1. **Fork the repository**
2. **Create a feature branch** from `main`
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes**
   - Follow the existing code style
   - Add comments for complex logic
   - Update documentation if needed
4. **Test your changes**
   ```bash
   export TELEGRAM_BOT_TOKEN="your-test-token"
   export TELEGRAM_CHAT_ID="your-test-chat"
   python send_video.py
   ```
5. **Commit with a clear message**
   ```bash
   git commit -m "Add feature: brief description"
   ```
6. **Push and create a Pull Request**

## Development Setup

### Prerequisites

- Python 3.11+
- A test Telegram bot (create via @BotFather)

### Installation

```bash
git clone https://github.com/YOUR_USERNAME/daf-yomi-history-bot.git
cd daf-yomi-history-bot
pip install -r requirements.txt
```

### Running Tests

```bash
# Test the scraper without sending to Telegram
python test_scraper.py

# Test the full flow
export TELEGRAM_BOT_TOKEN="your-token"
export TELEGRAM_CHAT_ID="your-chat-id"
python send_video.py
```

## Code Style

- Use descriptive variable names
- Add docstrings to functions
- Keep functions focused and small
- Handle errors gracefully with informative messages

## Questions?

Open an issue with the "question" label, and we'll be happy to help.
