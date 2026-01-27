# Security Policy

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

## Security Considerations

### Secrets Management

- **Never commit** `TELEGRAM_BOT_TOKEN` or `TELEGRAM_CHAT_ID` to the repository
- Always use GitHub Secrets for sensitive values
- Rotate your bot token if you suspect it's compromised

### Bot Token Security

If your bot token is exposed:

1. Go to [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/revoke` and select your bot
3. Update the `TELEGRAM_BOT_TOKEN` secret in GitHub

### Third-Party Dependencies

This project uses minimal dependencies to reduce attack surface:

- `httpx` — HTTP client
- `beautifulsoup4` — HTML parsing
- `python-telegram-bot` — Telegram API wrapper

Dependencies are pinned in `requirements.txt`. Regularly check for security updates.

## Best Practices for Users

1. **Use a dedicated bot** — Don't reuse bot tokens across projects
2. **Private repository** — Keep your fork private if you customize it
3. **Review Actions logs** — Check for unexpected behavior periodically
