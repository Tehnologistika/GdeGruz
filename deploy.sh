#!/bin/sh
cd ~/fleet-live-bot
git pull origin main
docker compose pull
docker compose up -d --build
docker image prune -f
