# Daf Yomi History Bot

A Telegram bot that delivers daily Jewish History videos from [AllDaf.org](https://alldaf.org)'s series by Dr. Henry Abramson, matching the Daf Yomi schedule.

[![Daily Video](https://github.com/naorbrown/daf-yomi-history-bot/actions/workflows/daily_video.yml/badge.svg)](https://github.com/naorbrown/daf-yomi-history-bot/actions/workflows/daily_video.yml)
[![CI](https://github.com/naorbrown/daf-yomi-history-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/naorbrown/daf-yomi-history-bot/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Start Using the Bot

1. **Open Telegram** on your phone or computer
2. **Search for** `@DafHistoryBot`
3. **Tap Start**

You'll receive a daily video every morning at 6:00 AM Israel time.

> **Quick link:** [t.me/DafHistoryBot](https://t.me/DafHistoryBot)

---

## How It Works

This bot runs entirely on **GitHub Actions** - no servers required.

| Workflow | Schedule | Purpose |
|----------|----------|---------|
| `daily_video.yml` | 6:00 AM Israel | Send daily history video |
| `poll-commands.yml` | Every 5 minutes | Process bot commands |
| `ci.yml` | On push/PR | Run tests |

### Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/today` | Get today's video |
| `/help` | Show help |

Note: Commands are processed every 5 minutes (GitHub Actions limitation).

---

## For Developers

### Quick Setup (5 minutes)

#### Step 1: Fork This Repository

Click the **Fork** button at the top right.

#### Step 2: Create a Telegram Bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot`
3. Choose a name and username
4. Save the **bot token** (looks like `123456:ABC-DEF1234...`)

#### Step 3: Get Your Chat ID

1. Message your new bot (send any message)
2. Visit: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. Find `"chat":{"id":123456789}` in the response

#### Step 4: Add GitHub Secrets

Go to your fork → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret Name | Value |
|-------------|-------|
| `TELEGRAM_BOT_TOKEN` | Your bot token from Step 2 |
| `TELEGRAM_CHAT_ID` | Your chat ID from Step 3 |

#### Step 5: Enable GitHub Actions

Go to **Actions** tab → Click **"I understand my workflows, go ahead and enable them"**

Done! Daily videos will send at 6:00 AM Israel time.

---

### Project Structure

```
daf-yomi-history-bot/
├── send_video.py              # Daily broadcast script
├── scripts/
│   └── poll_commands.py       # Command polling for GitHub Actions
├── src/                       # Core modules
│   ├── command_parser.py      # Command parsing utilities
│   ├── rate_limiter.py        # Rate limiting (5 req/min/user)
│   └── message_builder.py     # Message formatting
├── tests/
│   ├── unit/                  # Unit tests (pytest)
│   └── test_bot.py            # Integration tests
├── test_apis.py               # API integration test script
├── .github/
│   ├── workflows/
│   │   ├── daily_video.yml    # Daily 6AM video sender
│   │   ├── poll-commands.yml  # Command polling (every 5 min)
│   │   └── ci.yml             # CI pipeline
│   └── state/                 # Bot state (auto-updated)
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

---

## Testing

```bash
# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-cov pytest-asyncio pyyaml

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=src --cov-report=term-missing

# Run API integration tests
python test_apis.py
```

### Local Bot Testing

To test the bot command polling locally:

```bash
# Set your bot token
export TELEGRAM_BOT_TOKEN="your-token-here"

# Run the poll script
python scripts/poll_commands.py
```

The script will:
1. Initialize state on first run (skips old messages)
2. Fetch new updates from Telegram
3. Process any pending commands
4. Log all activity to console

---

## Cost

**Free. Forever.**

| Service | Cost |
|---------|------|
| GitHub Actions | Free (public repos) |
| Hebcal API | Free |
| AllDaf.org | Free |
| Telegram Bot API | Free |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Video not found | Video may not exist for today's daf - check [AllDaf](https://alldaf.org/series/3940) |
| Wrong daf displayed | Bot uses Israel timezone - verify at [Hebcal](https://www.hebcal.com/sedrot) |
| Daily video not sending | Check GitHub Actions logs in your fork |
| Commands slow | Commands poll every 5 min - this is a GitHub Actions limitation |
| Commands not responding | Check Actions → Poll Bot Commands workflow is running and not failing |
| Bot responds to old messages | State file may be missing - workflow will auto-initialize on next run |

---

## License

MIT — see [LICENSE](LICENSE).

---

## Acknowledgments

- [AllDaf.org](https://alldaf.org) & the Orthodox Union
- [Dr. Henry Abramson](https://www.henryabramson.com/)
- [Hebcal](https://www.hebcal.com/)

---

*Not affiliated with AllDaf.org, the Orthodox Union, or Hebcal.*
