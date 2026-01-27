# Daf Yomi History Bot

A Telegram bot that delivers daily Jewish History videos from [AllDaf.org](https://alldaf.org)'s series by Dr. Henry Abramson, matching the Daf Yomi schedule.

[![Daily Video](https://github.com/naorbrown/daf-yomi-history-bot/actions/workflows/daily_video.yml/badge.svg)](https://github.com/naorbrown/daf-yomi-history-bot/actions/workflows/daily_video.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

---

## 🚀 Start Using the Bot

**Open Telegram and start chatting:**

1. **Open Telegram** on your phone or computer
2. **Search for** `@DafHistoryBot`
3. **Tap Start**

That's it! You'll receive a daily video at 1:30 AM Israel time.

> **Quick link:** [t.me/DafHistoryBot](https://t.me/DafHistoryBot)

---

## 📱 Bot Commands

| Command | What It Does |
|---------|--------------|
| `/start` | Welcome message and instructions |
| `/today` | Get today's Daf Yomi history video |
| `/help` | Show all available commands |

---

## ❓ FAQ

### What is this bot?

This bot sends you a short Jewish History video every day, matching the Daf Yomi learning schedule. The videos are from Dr. Henry Abramson's series on AllDaf.org.

### When do I get videos?

- **Automatically** every day at 1:30 AM Israel time
- **On-demand** anytime by sending `/today`

### Is it free?

Yes, completely free. No ads, no subscriptions, no catches.

### Do I need to do anything after starting?

No! Just tap Start once, and you'll receive videos automatically every day.

---

## 🛠 For Developers

Want to run your own instance? See the [Developer Guide](#developer-guide) below.

---

## Developer Guide

### Prerequisites

- A Telegram account
- A GitHub account

### Quick Setup

#### 1. Fork This Repository

Click the **Fork** button at the top right.

#### 2. Create a Telegram Bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot`
3. Choose a name and username
4. Save the **bot token**

#### 3. Get Your Chat ID

1. Message your new bot
2. Visit: `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Find your Chat ID in the response

#### 4. Add GitHub Secrets

Go to your fork → **Settings** → **Secrets and variables** → **Actions**

| Secret Name | Value |
|-------------|-------|
| `TELEGRAM_BOT_TOKEN` | Your bot token |
| `TELEGRAM_CHAT_ID` | Your chat ID |

#### 5. Enable GitHub Actions

Go to **Actions** tab → Enable workflows

✅ Done! Videos will be sent daily at 1:30 AM Israel time.

### Running the Interactive Bot

The `/today` command requires the bot to run continuously. To enable it:

```bash
# Install dependencies
pip install httpx beautifulsoup4 python-telegram-bot

# Set your token
export TELEGRAM_BOT_TOKEN="your-token-here"

# Run the bot
python bot.py
```

Options for hosting:
- **Local machine** (must stay running)
- **Raspberry Pi** (low-power, always-on)
- **Free cloud tier** (Railway, Render, Fly.io)

---

## 📖 How It Works

```
┌─────────────────┐     ┌─────────────┐     ┌─────────────┐     ┌──────────┐
│ GitHub Actions  │────▶│ Hebcal API  │────▶│ AllDaf.org  │────▶│ Telegram │
│ (1:30 AM IST)   │     │ (Get Daf)   │     │ (Get Video) │     │ (Send)   │
└─────────────────┘     └─────────────┘     └─────────────┘     └──────────┘
```

---

## 💰 Cost

**Free. Forever.**

| Service | Cost |
|---------|------|
| GitHub Actions | Free (public repos) |
| Hebcal API | Free |
| AllDaf.org | Free |
| Telegram Bot API | Free |

---

## 🔒 Security

Zero-attack-surface architecture:

- ❌ No server running (for GitHub Actions version)
- ❌ No webhooks or open ports
- ❌ No database
- ✅ Only outbound HTTPS requests

See [SECURITY.md](SECURITY.md) for details.

---

## 📁 Files

| File | Purpose |
|------|---------|
| `send_video.py` | Scheduled sender (GitHub Actions) |
| `bot.py` | Interactive bot (responds to /today) |
| `daily_video.yml` | GitHub Actions workflow |

---

## 🐛 Troubleshooting

**Video not found** — The video may not exist for today's daf yet. Check [AllDaf](https://alldaf.org/series/3940).

**Wrong daf** — Bot uses Israel timezone. Verify at [Hebcal](https://www.hebcal.com/sedrot).

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 📜 License

MIT — see [LICENSE](LICENSE).

---

## 🙏 Acknowledgments

- [AllDaf.org](https://alldaf.org) & the Orthodox Union
- [Dr. Henry Abramson](https://www.henryabramson.com/)
- [Hebcal](https://www.hebcal.com/)

---

*Not affiliated with AllDaf.org, the Orthodox Union, or Hebcal.*
