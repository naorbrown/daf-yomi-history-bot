#!/bin/bash
#
# Daf Yomi History Bot - Webhook Setup Script
#
# This script helps you set up the Telegram webhook for your bot.
# Run this after deploying to Vercel.
#
# Usage:
#   ./scripts/setup_webhook.sh
#
# Or with arguments:
#   ./scripts/setup_webhook.sh <BOT_TOKEN> <VERCEL_URL>
#

set -e

echo "========================================"
echo "  Daf Yomi History Bot - Webhook Setup"
echo "========================================"
echo ""

# Get bot token
if [ -n "$1" ]; then
    BOT_TOKEN="$1"
elif [ -n "$TELEGRAM_BOT_TOKEN" ]; then
    BOT_TOKEN="$TELEGRAM_BOT_TOKEN"
else
    echo "Enter your Telegram Bot Token:"
    echo "(Get this from @BotFather on Telegram)"
    read -r BOT_TOKEN
fi

if [ -z "$BOT_TOKEN" ]; then
    echo "ERROR: Bot token is required"
    exit 1
fi

# Get Vercel URL
if [ -n "$2" ]; then
    VERCEL_URL="$2"
else
    echo ""
    echo "Enter your Vercel deployment URL:"
    echo "(e.g., https://daf-yomi-history-bot.vercel.app)"
    read -r VERCEL_URL
fi

if [ -z "$VERCEL_URL" ]; then
    echo "ERROR: Vercel URL is required"
    exit 1
fi

# Remove trailing slash if present
VERCEL_URL="${VERCEL_URL%/}"

# Construct webhook URL
WEBHOOK_URL="${VERCEL_URL}/api/webhook"

echo ""
echo "----------------------------------------"
echo "Configuration:"
echo "  Bot Token: ${BOT_TOKEN:0:10}..."
echo "  Webhook URL: $WEBHOOK_URL"
echo "----------------------------------------"
echo ""

# Step 1: Check current webhook status
echo "Step 1: Checking current webhook status..."
CURRENT_WEBHOOK=$(curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo")
echo "Current webhook info:"
echo "$CURRENT_WEBHOOK" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d, indent=2))" 2>/dev/null || echo "$CURRENT_WEBHOOK"
echo ""

# Step 2: Test the Vercel endpoint
echo "Step 2: Testing Vercel endpoint..."
HEALTH_CHECK=$(curl -s -w "\nHTTP_CODE:%{http_code}" "${VERCEL_URL}/api/webhook" 2>/dev/null || echo "FAILED")
echo "Health check response:"
echo "$HEALTH_CHECK"
echo ""

# Step 3: Set the webhook
echo "Step 3: Setting webhook..."
SET_RESULT=$(curl -s "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=${WEBHOOK_URL}")
echo "Set webhook result:"
echo "$SET_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d, indent=2))" 2>/dev/null || echo "$SET_RESULT"
echo ""

# Step 4: Verify webhook was set
echo "Step 4: Verifying webhook..."
VERIFY_WEBHOOK=$(curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo")
echo "Webhook info after setting:"
echo "$VERIFY_WEBHOOK" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d, indent=2))" 2>/dev/null || echo "$VERIFY_WEBHOOK"
echo ""

# Check if webhook URL matches
if echo "$VERIFY_WEBHOOK" | grep -q "$WEBHOOK_URL"; then
    echo "========================================"
    echo "  ✅ SUCCESS! Webhook is configured"
    echo "========================================"
    echo ""
    echo "Your bot should now respond to commands."
    echo "Try sending /start to your bot on Telegram."
else
    echo "========================================"
    echo "  ❌ WARNING: Webhook may not be set correctly"
    echo "========================================"
    echo ""
    echo "Please check:"
    echo "1. Your bot token is correct"
    echo "2. Your Vercel URL is correct"
    echo "3. TELEGRAM_BOT_TOKEN is set in Vercel environment variables"
fi

echo ""
echo "Done!"
