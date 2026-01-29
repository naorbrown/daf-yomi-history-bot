# Daf Yomi History Bot

A Telegram bot that delivers daily Jewish History videos from [AllDaf.org](https://alldaf.org)'s series by Dr. Henry Abramson, matching the Daf Yomi schedule.

[![Daily Video](https://github.com/naorbrown/daf-yomi-history-bot/actions/workflows/daily_video.yml/badge.svg)](https://github.com/naorbrown/daf-yomi-history-bot/actions/workflows/daily_video.yml)
[![CI/CD](https://github.com/naorbrown/daf-yomi-history-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/naorbrown/daf-yomi-history-bot/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

---

## Start Using the Bot

1. **Open Telegram** on your phone or computer
2. **Search for** `@DafHistoryBot`
3. **Tap Start**

You'll receive a daily video every morning at 6:00 AM Israel time.

> **Quick link:** [t.me/DafHistoryBot](https://t.me/DafHistoryBot)

---

## How It Works

This bot uses **GitHub Actions** to automatically send daily videos:

```
┌─────────────────────────────────────────────────────────────────┐
│                    DAF YOMI HISTORY BOT                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────┐              ┌─────────────────┐         │
│   │ GitHub Actions  │              │   Telegram      │         │
│   │ (Daily 6AM IST) │─────────────▶│   Bot API       │         │
│   └─────────────────┘              └─────────────────┘         │
│            │                                                    │
│            ▼                                                    │
│   ┌─────────────────────────────────────────┐                  │
│   │           External APIs                  │                  │
│   │  • Hebcal (Daf Yomi schedule)           │                  │
│   │  • AllDaf.org (Video content)           │                  │
│   └─────────────────────────────────────────┘                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Daily at 6:00 AM Israel time**, GitHub Actions:
1. Fetches today's Daf from Hebcal API
2. Finds the matching video on AllDaf.org
3. Sends it to all subscribers via Telegram

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

✅ **Done!** Daily videos will send at 6:00 AM Israel time.

---

### Project Structure

```
daf-yomi-history-bot/
├── send_video.py           # Main script - sends daily video
├── bot.py                  # Interactive bot (for local testing)
├── src/                    # Core modules
│   ├── command_parser.py   # Command parsing utilities
│   ├── rate_limiter.py     # Rate limiting (5 req/min/user)
│   └── message_builder.py  # Message formatting
├── tests/
│   ├── unit/               # Unit tests (pytest)
│   └── test_bot.py         # Integration tests
├── test_apis.py            # API integration test script
├── .github/workflows/
│   ├── daily_video.yml     # Daily 6AM video sender
│   └── ci.yml              # CI/CD pipeline
├── requirements.txt        # Python dependencies
├── README.md               # This file
└── SECURITY.md             # Security documentation
```

---

## Testing

### Run Tests Locally

```bash
# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-cov pyyaml

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=src --cov-report=term-missing

# Run API integration tests
python test_apis.py
```

### Test Coverage

| Module | Tests | Coverage |
|--------|-------|----------|
| `command_parser` | 25 tests | Command parsing, bot mentions, edge cases |
| `rate_limiter` | 14 tests | Rate limiting, per-user tracking |
| `message_builder` | 23 tests | Message formatting, video captions |
| `integration` | 17 tests | Workflow validation, file checks |

### CI/CD Pipeline

Every push and PR automatically runs:

1. **Unit Tests** - All modules tested with pytest
2. **Integration Tests** - API connectivity checks
3. **Linting** - Code quality (Ruff)
4. **Security Scan** - Dependency vulnerabilities
5. **Validation** - Workflow and config verification

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
| Workflow failing | Run `pytest tests/ -v` locally to debug |

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

---

*Not affiliated with AllDaf.org, the Orthodox Union, or Hebcal.*
