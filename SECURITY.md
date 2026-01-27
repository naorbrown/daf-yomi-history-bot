# Security Policy

## Security Architecture

This project is designed with a **zero-attack-surface architecture**:

### No Inbound Connections

```
┌─────────────────────────────────────────────────────────────────┐
│                     SECURITY MODEL                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ❌ NO server running                                          │
│   ❌ NO webhook endpoints                                       │
│   ❌ NO listening ports                                         │
│   ❌ NO bot command handlers                                    │
│   ❌ NO user input processing                                   │
│   ❌ NO database or storage                                     │
│   ❌ NO authentication system to exploit                        │
│                                                                  │
│   ✅ ONLY outbound HTTPS requests                               │
│   ✅ ONLY runs on GitHub's infrastructure                       │
│   ✅ ONLY triggered by schedule (no external triggers)          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Why This Is Secure

| Attack Vector | Protection |
|--------------|------------|
| **Remote Code Execution** | No server = nothing to exploit |
| **DDoS Attacks** | No endpoints = nothing to attack |
| **Bot Command Injection** | No command handlers = no processing of user messages |
| **SQL Injection** | No database = no SQL |
| **Authentication Bypass** | No auth system = nothing to bypass |
| **Man-in-the-Middle** | All connections use HTTPS |
| **Unauthorized Triggers** | Only GitHub cron + repo owner can trigger |

### Cost Protection

**This project is 100% free forever:**

- ✅ GitHub Actions: Free for public repositories (unlimited minutes)
- ✅ Hebcal API: Free, no API key required
- ✅ AllDaf.org: Public website, no API key
- ✅ Telegram Bot API: Free, unlimited messages

**There is no possible way to incur charges** because:
- No paid APIs are used
- No cloud infrastructure beyond GitHub Actions
- No databases, storage, or compute resources
- GitHub Actions cannot bill you for public repos

## Workflow Security Hardening

The GitHub Actions workflow includes these security measures:

```yaml
permissions:
  contents: read  # Minimum permissions - read only

concurrency:
  group: daily-video  # Prevents duplicate runs

timeout-minutes: 5  # Kills runaway processes

persist-credentials: false  # No git credentials stored
```

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| latest  | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do not** open a public issue
2. Email the maintainer directly or use GitHub's private vulnerability reporting
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

## Secrets Management

### Required Secrets

- **Never commit** `TELEGRAM_BOT_TOKEN` or `TELEGRAM_CHAT_ID` to the repository
- Always use GitHub Secrets for sensitive values
- Rotate your bot token if you suspect it's compromised

### Bot Token Security

If your bot token is exposed:

1. Go to [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/revoke` and select your bot
3. Update the `TELEGRAM_BOT_TOKEN` secret in GitHub

### What Happens If Someone Gets Your Token?

Even if someone obtained your bot token, they could only:
- Send messages AS your bot (not receive or read messages)
- They cannot access your Telegram account
- They cannot run the GitHub workflow
- They cannot modify the code

**Mitigation**: Simply revoke the token via BotFather.

## Third-Party Dependencies

This project uses minimal dependencies to reduce attack surface:

| Package | Purpose | Security Notes |
|---------|---------|----------------|
| `httpx` | HTTP client | Well-audited, async-native |
| `beautifulsoup4` | HTML parsing | No network access |
| `python-telegram-bot` | Telegram API | Official wrapper |

## Fork Security

If you fork this repository:

1. **Add your own secrets** — Forked repos don't inherit secrets
2. **Enable Actions** — You must manually enable GitHub Actions
3. **Review the code** — Understand what runs before enabling

## Audit Trail

All workflow runs are logged in GitHub Actions with:
- Exact timestamp
- Full execution logs
- Success/failure status

View at: `https://github.com/YOUR_USERNAME/daf-yomi-history-bot/actions`
