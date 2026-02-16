# Daf Yomi History Telegram Bot

A Telegram bot that sends the daily Daf Yomi Jewish History video from [AllDaf.org](https://alldaf.org) every morning at 3:00 AM Israel time.

## Features

- Fetches the current Daf Yomi from [Sefaria's API](https://www.sefaria.org)
- Finds the corresponding Jewish History in Daf Yomi video by Dr. Henry Abramson
- Sends a message with the video link to your Telegram chat
- Runs automatically every day at 3:00 AM Israel time

## Setup

### 1. Create a Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts to create your bot
3. Copy the bot token (looks like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Get Your Chat ID

1. Start a chat with your new bot (search for it and click Start)
2. Send any message to the bot
3. Visit `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Find your chat ID in the response (looks like `123456789`)

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Environment Variables

```bash
export TELEGRAM_BOT_TOKEN="your-bot-token-here"
export TELEGRAM_CHAT_ID="your-chat-id-here"
```

### 5. Run the Bot

```bash
python daf_yomi_bot.py
```

## Testing

To test the scraper without Telegram credentials:

```bash
python test_scraper.py
```

## Deployment Options

### Option 1: Run on a Server (VPS, Raspberry Pi, etc.)

Use a process manager like `systemd` or `supervisor` to keep the bot running.

Example systemd service (`/etc/systemd/system/daf-yomi-bot.service`):

```ini
[Unit]
Description=Daf Yomi History Telegram Bot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/daf-history
Environment=TELEGRAM_BOT_TOKEN=your-token
Environment=TELEGRAM_CHAT_ID=your-chat-id
ExecStart=/usr/bin/python3 daf_yomi_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable daf-yomi-bot
sudo systemctl start daf-yomi-bot
```

### Option 2: Docker

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY daf_yomi_bot.py .

CMD ["python", "daf_yomi_bot.py"]
```

Build and run:
```bash
docker build -t daf-yomi-bot .
docker run -d \
  -e TELEGRAM_BOT_TOKEN="your-token" \
  -e TELEGRAM_CHAT_ID="your-chat-id" \
  --name daf-yomi-bot \
  --restart unless-stopped \
  daf-yomi-bot
```

### Option 3: Cloud Functions (e.g., AWS Lambda, Google Cloud Functions)

For serverless deployment, you'll need to:
1. Remove the scheduler and just run `send_daily_video()` directly
2. Set up a cloud scheduler (CloudWatch Events, Cloud Scheduler) to trigger at 3:00 AM Israel time
3. Configure environment variables in your cloud platform

## Troubleshooting

- **Bot not sending messages**: Check that both environment variables are set correctly
- **Video not found**: The AllDaf website structure may have changed; check the series page manually
- **Wrong daf**: The bot uses Sefaria's calendar, which should always be accurate

## License

MIT
