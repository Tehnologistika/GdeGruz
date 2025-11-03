#!/bin/bash
# Script to add DOCUMENTS_GROUP_ID to .env file on the server
# Usage: ./update_documents_group.sh

set -e

ENV_FILE="/home/git/fleet-live-bot/.env"
DOCUMENTS_GROUP_ID="-5054329274"

echo "🔧 Updating .env file with DOCUMENTS_GROUP_ID..."

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Error: .env file not found at $ENV_FILE"
    echo "Please create it first by copying from .env.example"
    exit 1
fi

# Check if DOCUMENTS_GROUP_ID already exists
if grep -q "^DOCUMENTS_GROUP_ID=" "$ENV_FILE"; then
    echo "⚠️  DOCUMENTS_GROUP_ID already exists in .env"
    echo "Current value:"
    grep "^DOCUMENTS_GROUP_ID=" "$ENV_FILE"
    read -p "Do you want to update it? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Update existing value
        sed -i "s/^DOCUMENTS_GROUP_ID=.*/DOCUMENTS_GROUP_ID=$DOCUMENTS_GROUP_ID/" "$ENV_FILE"
        echo "✅ Updated DOCUMENTS_GROUP_ID=$DOCUMENTS_GROUP_ID"
    else
        echo "❌ Cancelled"
        exit 0
    fi
else
    # Add new value
    echo "" >> "$ENV_FILE"
    echo "# ID группы для документов" >> "$ENV_FILE"
    echo "DOCUMENTS_GROUP_ID=$DOCUMENTS_GROUP_ID" >> "$ENV_FILE"
    echo "✅ Added DOCUMENTS_GROUP_ID=$DOCUMENTS_GROUP_ID"
fi

echo ""
echo "📋 Current .env content:"
cat "$ENV_FILE"

echo ""
echo "🔄 Restarting bot to apply changes..."
cd /home/git/fleet-live-bot
docker compose restart bot

echo ""
echo "✅ Done! Check logs with: docker logs fleet-live-bot_bot_1 -f"
