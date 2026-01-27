# Daf Yomi History Bot

A Telegram bot that delivers daily Jewish History videos from [AllDaf.org](https://alldaf.org)'s "Jewish History in Daf Yomi" series by Dr. Henry Abramson.

[![Daily Video](https://github.com/naorbrown/daf-yomi-history-bot/actions/workflows/daily_video.yml/badge.svg)](https://github.com/naorbrown/daf-yomi-history-bot/actions/workflows/daily_video.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## Overview

Every morning at 1:30 AM Israel Time, this bot automatically:

1. Fetches the current Daf Yomi from [Hebcal's API](https://www.hebcal.com/home/developer-apis)
2. Finds the corresponding Jewish History video on AllDaf.org
3. Sends the video directly to your Telegram chat

## Features

- **Embedded Video Delivery** — Videos play directly in Telegram, no external links needed
- **Accurate Calendar** — Uses Hebcal API with Israel timezone for correct daily daf
- **Reliable Scheduling** — Runs via GitHub Actions, works 24/7 without any server
- **Zero Maintenance** — Set it up once, receive videos forever

## Quick Start

### Prerequisites

- A Telegram account
- A GitHub account

### Setup

1. **Fork this repository**

2. **Create a Telegram Bot**
   - Message [@BotFather](https://t.me/BotFather) on Telegram
   - Send `/newbot` and follow the prompts
   - Save the bot token (e.g., `123456789:ABCdefGHI...`)

3. **Get your Chat ID**
   - Start a chat with your new bot
   - Send any message
   - Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   - Find `"chat":{"id":123456789}` — that number is your Chat ID

4. **Add GitHub Secrets**
   - Go to your fork's Settings → Secrets and variables → Actions
   - Add two secrets:
     - `TELEGRAM_BOT_TOKEN`: Your bot token
     - `TELEGRAM_CHAT_ID`: Your chat ID

5. **Enable GitHub Actions**
   - Go to the Actions tab in your fork
   - Click "I understand my workflows, go ahead and enable them"

That's it! You'll receive your first video at 1:30 AM Israel Time.

### Manual Trigger

To test immediately or send a video on-demand:

```bash
gh workflow run daily_video.yml
```

Or use the GitHub Actions UI: Actions → Send Daily Daf Yomi History Video → Run workflow

## Configuration

| Environment Variable | Description | Required |
|---------------------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | Yes |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID | Yes |

## Architecture

```
┌─────────────────┐     ┌─────────────┐     ┌─────────────┐     ┌──────────┐
│ GitHub Actions  │────▶│ Hebcal API  │────▶│ AllDaf.org  │────▶│ Telegram │
│ (1:30 AM IST)   │     │ (Get Daf)   │     │ (Get Video) │     │ (Send)   │
└─────────────────┘     └─────────────┘     └─────────────┘     └──────────┘
```

## API Dependencies

- **[Hebcal API](https://www.hebcal.com/home/developer-apis)** — Jewish calendar data (free, no auth required)
- **[AllDaf.org](https://alldaf.org)** — Video content from the OU's Torah learning platform
- **[Telegram Bot API](https://core.telegram.org/bots/api)** — Message delivery

## Development

### Local Testing

```bash
# Clone the repository
git clone https://github.com/naorbrown/daf-yomi-history-bot.git
cd daf-yomi-history-bot

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export TELEGRAM_BOT_TOKEN="your-token"
export TELEGRAM_CHAT_ID="your-chat-id"

# Run the script
python send_video.py
```

### Project Structure

```
├── .github/
│   └── workflows/
│       └── daily_video.yml    # GitHub Actions workflow
├── send_video.py              # Main script for GitHub Actions
├── daf_yomi_bot.py           # Standalone bot with scheduler (optional)
├── test_scraper.py           # Test script for debugging
├── requirements.txt          # Python dependencies
├── LICENSE                   # MIT License
└── README.md
```

## Troubleshooting

### Video not found

The AllDaf website occasionally changes structure. If the bot fails to find a video:

1. Check the [Actions logs](../../actions) for error details
2. Verify the video exists on [AllDaf's Jewish History series](https://alldaf.org/series/3940)
3. Open an issue with the masechta and daf number

### Wrong daf

The bot uses Israel timezone. If the daf seems off:

1. Check the current time in Israel
2. Verify against [Hebcal's calendar](https://www.hebcal.com/sedrot)

### Bot not responding

1. Verify your bot token is correct
2. Ensure you've started a chat with the bot
3. Check that the Chat ID matches your conversation

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [AllDaf.org](https://alldaf.org) and the Orthodox Union for the Jewish History video series
- [Dr. Henry Abramson](https://www.henryabramson.com/) for creating the Jewish History in Daf Yomi content
- [Hebcal](https://www.hebcal.com/) for their excellent Jewish calendar API

## Disclaimer

This project is not affiliated with AllDaf.org, the Orthodox Union, or Hebcal. It simply provides a convenient way to receive publicly available educational content via Telegram.
