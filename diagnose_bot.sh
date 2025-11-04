#!/bin/bash
# Diagnostic script for bot issues

echo "==================================="
echo "🔍 BOT DIAGNOSTIC SCRIPT"
echo "==================================="
echo ""

echo "📋 1. Checking Docker containers status..."
docker ps -a | grep fleet-live-bot

echo ""
echo "📋 2. Last 50 lines of bot logs..."
docker logs fleet-live-bot_bot_1 --tail 50 2>&1

echo ""
echo "📋 3. Checking .env file..."
if [ -f "/home/git/fleet-live-bot/.env" ]; then
    echo "✅ .env file exists"
    echo "Environment variables (secrets hidden):"
    grep -v "TOKEN\|SECRET" /home/git/fleet-live-bot/.env || echo "No non-secret vars found"
    echo ""
    echo "DOCUMENTS_GROUP_ID value:"
    grep "DOCUMENTS_GROUP_ID" /home/git/fleet-live-bot/.env || echo "❌ DOCUMENTS_GROUP_ID not found!"
else
    echo "❌ .env file NOT found at /home/git/fleet-live-bot/.env"
fi

echo ""
echo "📋 4. Checking Python syntax..."
cd /home/git/fleet-live-bot
python3 -m py_compile db_documents.py 2>&1 && echo "✅ db_documents.py - OK" || echo "❌ db_documents.py - SYNTAX ERROR"
python3 -m py_compile bot/handlers/documents.py 2>&1 && echo "✅ bot/handlers/documents.py - OK" || echo "❌ bot/handlers/documents.py - SYNTAX ERROR"
python3 -m py_compile bot/main.py 2>&1 && echo "✅ bot/main.py - OK" || echo "❌ bot/main.py - SYNTAX ERROR"

echo ""
echo "📋 5. Checking file structure..."
ls -la /home/git/fleet-live-bot/db_documents.py
ls -la /home/git/fleet-live-bot/bot/handlers/documents.py

echo ""
echo "==================================="
echo "✅ Diagnostic complete"
echo "==================================="
