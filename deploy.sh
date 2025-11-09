#!/bin/sh
# Определяем правильный путь к проекту
PROJECT_DIR="${PROJECT_DIR:-/home/git/fleet-live-bot}"

cd "$PROJECT_DIR" || exit 1

echo "🔄 Pulling latest changes from main..."
git pull origin main

# Проверяем, нужно ли очистить БД
if [ -f ".cleanup_db_on_deploy" ]; then
    echo "🧹 Обнаружен флаг очистки БД, выполняем очистку тестовых данных..."

    # Запускаем скрипт очистки через Docker
    docker compose run --rm bot python cleanup_test_data.py

    # Удаляем флаг после успешной очистки
    if [ $? -eq 0 ]; then
        rm -f ".cleanup_db_on_deploy"
        echo "✅ База данных очищена, флаг удален"
    else
        echo "❌ Ошибка при очистке базы данных"
    fi
fi

echo "🐳 Building and starting containers..."
docker compose pull
docker compose up -d --build

echo "🧹 Cleaning up old images..."
docker image prune -f

echo "✅ Deployment completed!"
