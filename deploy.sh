#!/bin/sh
# Определяем правильный путь к проекту
PROJECT_DIR="${PROJECT_DIR:-/home/git/fleet-live-bot}"

cd "$PROJECT_DIR" || exit 1
git pull origin main
docker compose pull
docker compose up -d --build
docker image prune -f
