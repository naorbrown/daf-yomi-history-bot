# Daf Yomi History Bot

A Telegram bot that delivers daily Jewish History videos from [AllDaf.org](https://alldaf.org)'s series by Dr. Henry Abramson, matching the Daf Yomi schedule.

[![Daily Video](https://github.com/naorbrown/daf-yomi-history-bot/actions/workflows/daily_video.yml/badge.svg)](https://github.com/naorbrown/daf-yomi-history-bot/actions/workflows/daily_video.yml)
[![CI/CD](https://github.com/naorbrown/daf-yomi-history-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/naorbrown/daf-yomi-history-bot/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

---

## Start Using the Bot

**Open Telegram and start chatting:**

1. **Open Telegram** on your phone or computer
2. **Search for** `@DafHistoryBot`
3. **Tap Start**

That's it! You'll receive a daily video every morning at 6:00 AM Israel time.

> **Quick link:** [t.me/DafHistoryBot](https://t.me/DafHistoryBot)

---

## Bot Commands

| Command | What It Does |
|---------|--------------|
| `/start` | Welcome message and instructions |
| `/today` | Get today's Daf Yomi history video |
| `/help` | Show all available commands |

---

## FAQ

### What is this bot?

This bot sends you a short Jewish History video every day, matching the Daf Yomi learning schedule. The videos are from Dr. Henry Abramson's series on AllDaf.org.

### When do I get videos?

- **Automatically** every morning at 6:00 AM Israel time
- **On-demand** anytime by sending `/today`

### Is it free?

Yes, completely free. No ads, no subscriptions, no catches.

### Do I need to do anything after starting?

No! Just tap Start once, and you'll receive videos automatically every day.

---

## For Developers

Want to run your own instance? See the [Developer Guide](#developer-guide) below.

---

## Developer Guide

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DAF YOMI HISTORY BOT                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐  │
│   │ GitHub Actions  │     │    Railway      │     │   Telegram      │  │
│   │ (Daily Videos)  │     │ (Bot Polling)   │     │   Bot API       │  │
│   └────────┬────────┘     └────────┬────────┘     └────────┬────────┘  │
│            │                       │                       │           │
│            ▼                       ▼                       │           │
│   ┌─────────────────┐     ┌─────────────────┐              │           │
│   │ Daily 6AM IST   │     │  Bot Commands   │◀─────────────┘           │
│   │ send_video.py   │     │    bot.py       │                          │
│   └────────┬────────┘     └────────┬────────┘                          │
│            │                       │                                    │
│            └───────────┬───────────┘                                    │
│                        ▼                                                │
│            ┌─────────────────────┐                                      │
│            │   External APIs     │                                      │
│            │ • Hebcal (Daf info) │                                      │
│            │ • AllDaf (Videos)   │                                      │
│            └─────────────────────┘                                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Prerequisites

- A Telegram account
- A GitHub account
- A Railway account (free) - for interactive bot commands

---

### Quick Setup

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

✅ **Daily videos are now configured!** They'll send at 6:00 AM Israel time.

---

### Enable Interactive Commands (Railway Deployment)

To make `/today`, `/start`, and `/help` work for any user, deploy to Railway:

#### Step 1: Deploy to Railway

1. Go to [railway.app](https://railway.app) and sign up (free)
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Select your forked repository
4. Add environment variable: `TELEGRAM_BOT_TOKEN`
5. Railway will auto-detect the `Procfile` and deploy `bot.py`

#### Step 2: Verify Bot is Running

Check Railway logs - you should see "Starting Daf Yomi History Bot (polling mode)..."

✅ **Done!** Commands now work for all users.

---

### Project Structure

```
daf-yomi-history-bot/
├── src/                    # Core modules
│   ├── __init__.py         # Package exports
│   ├── command_parser.py   # Command parsing and validation
│   ├── rate_limiter.py     # Per-user rate limiting (5 req/min)
│   └── message_builder.py  # Message formatting utilities
├── tests/
│   ├── unit/               # Unit tests (pytest)
│   │   ├── test_command_parser.py
│   │   ├── test_rate_limiter.py
│   │   └── test_message_builder.py
│   ├── fixtures/           # Test fixtures and mock data
│   └── test_bot.py         # Integration tests
├── .github/
│   └── workflows/
│       ├── daily_video.yml # Scheduled daily video sender (6 AM Israel)
│       └── ci.yml          # CI/CD pipeline (tests, lint, security)
├── bot.py                  # Telegram bot with polling (Railway)
├── send_video.py           # GitHub Actions video sender
├── test_apis.py            # API integration test script
├── Procfile                # Railway deployment config
├── railway.toml            # Railway settings
├── requirements.txt        # Python dependencies
├── README.md               # This file
└── SECURITY.md             # Security documentation
```

---

## Cost

**Free. Forever.**

| Service | Cost | Purpose |
|---------|------|---------|
| GitHub Actions | Free (public repos) | Daily scheduled videos |
| Railway | Free (hobby tier) | Interactive bot commands |
| Hebcal API | Free | Daf Yomi schedule |
| AllDaf.org | Free | Video content |
| Telegram Bot API | Free | Message delivery |

---

## Security

Production-grade security:

- ✅ No stored credentials in code
- ✅ Environment variables for secrets
- ✅ HTTPS-only communication
- ✅ Minimal dependencies
- ✅ Automated security scanning in CI/CD
- ✅ No database or persistent storage

See [SECURITY.md](SECURITY.md) for detailed security architecture.

---

## Testing & QA

### Run Tests Locally

```bash
# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-cov

# Run all unit tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_command_parser.py -v

# Run API integration tests
python test_apis.py
```

### Test Coverage

The test suite covers:

| Module | Tests | Coverage |
|--------|-------|----------|
| `command_parser` | 25 tests | Command parsing, bot mentions, edge cases |
| `rate_limiter` | 14 tests | Rate limiting, per-user tracking, window expiration |
| `message_builder` | 23 tests | Message formatting, video captions |

### CI/CD Pipeline

Every push and PR automatically runs:

1. **Unit Tests** - Verify all modules with pytest
2. **API Integration Tests** - Test external API connections
3. **Linting** - Code quality checks (Ruff)
4. **Security Scan** - Dependency vulnerability check
5. **Validation** - Config and syntax verification

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Bot doesn't respond to commands | Deploy to Railway and check logs |
| Video not found | Video may not exist for today's daf - check [AllDaf](https://alldaf.org/series/3940) |
| Wrong daf displayed | Bot uses Israel timezone - verify at [Hebcal](https://www.hebcal.com/sedrot) |
| Daily video not sending | Check GitHub Actions logs in your fork |

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`pytest tests/ -v`)
5. Commit (`git commit -m 'Add amazing feature'`)
6. Push (`git push origin feature/amazing-feature`)
7. Open a Pull Request

All PRs are automatically tested by CI/CD.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Acknowledgments

- [AllDaf.org](https://alldaf.org) & the Orthodox Union
- [Dr. Henry Abramson](https://www.henryabramson.com/)
- [Hebcal](https://www.hebcal.com/)
- [Railway](https://railway.app/) for free hosting

---

*Not affiliated with AllDaf.org, the Orthodox Union, or Hebcal.*
