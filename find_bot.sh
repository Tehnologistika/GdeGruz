#!/bin/bash
# Script to find the bot installation on the server

echo "🔍 Поиск бота GdeGruz на сервере..."
echo "=================================="
echo ""

echo "📋 1. Проверка запущенных Docker контейнеров:"
docker ps -a | grep -i "fleet\|gdegruz\|bot" || echo "❌ Docker контейнеры не найдены"

echo ""
echo "📋 2. Поиск папки fleet-live-bot:"
find /home -type d -name "fleet-live-bot" 2>/dev/null || echo "❌ Папка fleet-live-bot не найдена в /home"
find /opt -type d -name "fleet-live-bot" 2>/dev/null || echo "❌ Папка fleet-live-bot не найдена в /opt"
find /var -type d -name "fleet-live-bot" 2>/dev/null || echo "❌ Папка fleet-live-bot не найдена в /var"

echo ""
echo "📋 3. Поиск файла docker-compose.yml с ботом:"
find /home -name "docker-compose.yml" -exec grep -l "fleet-live-bot\|gdegruz" {} \; 2>/dev/null

echo ""
echo "📋 4. Поиск Python файлов с aiogram:"
find /home -name "main.py" -exec grep -l "aiogram" {} \; 2>/dev/null | head -5

echo ""
echo "📋 5. Проверка git репозиториев:"
find /home -type d -name ".git" 2>/dev/null | grep -v ".cache\|.local" | head -10

echo ""
echo "📋 6. Текущие пользователи с домашними папками:"
ls -la /home/

echo ""
echo "📋 7. Проверка docker volumes:"
docker volume ls | grep -i "fleet\|bot"

echo ""
echo "=================================="
echo "✅ Поиск завершен"
echo "=================================="
