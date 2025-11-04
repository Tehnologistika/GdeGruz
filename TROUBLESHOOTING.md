# 🚨 Инструкция по устранению проблем с ботом

## Шаг 1: Подключитесь к серверу

```bash
ssh user@your-server
cd /home/git/fleet-live-bot
```

## Шаг 2: Запустите диагностику

```bash
./diagnose_bot.sh
```

**Пришлите мне вывод этой команды!**

## Шаг 3: Быстрое исправление (попробуйте сразу)

### Вариант A: Откатиться к предыдущей версии

```bash
cd /home/git/fleet-live-bot
git checkout HEAD~2  # вернуться на 2 коммита назад
docker compose restart bot
docker logs fleet-live-bot_bot_1 -f
```

Если бот заработал - значит проблема в новом коде.

### Вариант B: Обновить код и перезапустить

```bash
cd /home/git/fleet-live-bot
git pull origin claude/document-management-system-011CUmN9GrnFqDZYHjmTdALk
docker compose down
docker compose up -d --build
docker logs fleet-live-bot_bot_1 -f
```

## Шаг 4: Проверьте типичные проблемы

### Проблема 1: Отсутствует DOCUMENTS_GROUP_ID

Проверьте:
```bash
cat /home/git/fleet-live-bot/.env | grep DOCUMENTS_GROUP_ID
```

Если нет - добавьте:
```bash
echo "" >> /home/git/fleet-live-bot/.env
echo "DOCUMENTS_GROUP_ID=-5054329274" >> /home/git/fleet-live-bot/.env
docker compose restart bot
```

### Проблема 2: Файлы не скопированы

Проверьте:
```bash
ls -la /home/git/fleet-live-bot/db_documents.py
ls -la /home/git/fleet-live-bot/bot/handlers/documents.py
```

Если файлов нет:
```bash
cd /home/git/fleet-live-bot
git pull origin claude/document-management-system-011CUmN9GrnFqDZYHjmTdALk
```

### Проблема 3: Ошибка импорта

Посмотрите последние строки логов:
```bash
docker logs fleet-live-bot_bot_1 --tail 30
```

Если видите `ModuleNotFoundError` или `ImportError` - пришлите мне полный вывод!

## Шаг 5: Полная перезагрузка

```bash
cd /home/git/fleet-live-bot
docker compose down
docker compose pull
docker compose up -d --build
docker logs fleet-live-bot_bot_1 -f
```

## Шаг 6: Просмотр логов в реальном времени

```bash
docker logs fleet-live-bot_bot_1 -f
```

Нажмите `Ctrl+C` для выхода.

## Шаг 7: Если ничего не помогает

### Откат к стабильной версии

```bash
cd /home/git/fleet-live-bot
git checkout main  # или другая стабильная ветка
docker compose down
docker compose up -d --build
```

## Полезные команды

### Посмотреть статус контейнеров
```bash
docker ps -a
```

### Посмотреть последние 100 строк логов
```bash
docker logs fleet-live-bot_bot_1 --tail 100
```

### Зайти внутрь контейнера
```bash
docker exec -it fleet-live-bot_bot_1 /bin/sh
```

### Проверить переменные окружения
```bash
docker exec fleet-live-bot_bot_1 env | grep DOCUMENTS
```

## Что мне прислать для анализа

1. Вывод команды `./diagnose_bot.sh`
2. Последние 50 строк логов: `docker logs fleet-live-bot_bot_1 --tail 50`
3. Вывод `docker ps -a`
4. Содержимое .env (без секретов): `cat .env | grep -v TOKEN`

После этого я смогу точно определить проблему!
