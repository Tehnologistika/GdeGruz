# Quick Start: Очистка БД GdeGruz

## Проблема

1. ✅ Тестовые рейсы остались в меню "Все рейсы" (куратор)
2. ⚠️ Появились нежелательные кнопки клавиатуры

## Причина

**GitHub Actions НЕ запускает cleanup скрипт!**

- `.github/workflows/deploy.yml` НЕ проверяет флаг `.cleanup_db_on_deploy`
- Флаг был создан, но никогда не обрабатывается
- deploy.yml НЕ использует deploy.sh (где есть логика очистки)

## Быстрое решение

### Вариант 1: Вручную на сервере (РЕКОМЕНДУЕТСЯ)

```bash
# 1. SSH на сервер
ssh username@host
cd /home/git/fleet-live-bot

# 2. Проверить текущее состояние
sqlite3 data/trips.db "SELECT COUNT(*) FROM trips;"

# 3. Очистить БД через Docker
docker compose run --rm bot python urgent_cleanup.py

# 4. Проверить результат
sqlite3 data/trips.db "SELECT COUNT(*) FROM trips;"
# Должно быть: 0
```

### Вариант 2: Напрямую SQL

```bash
sqlite3 data/trips.db "DELETE FROM trips;"
sqlite3 data/trips.db "DELETE FROM trip_events;"
sqlite3 data/trips.db "DELETE FROM sqlite_sequence WHERE name='trips';"
```

## Исправление деплоя

### Способ A: Обновить deploy.yml

Добавить в `.github/workflows/deploy.yml` перед `docker-compose down`:

```yaml
# Проверка флага очистки БД
if [ -f ".cleanup_db_on_deploy" ]; then
    echo "🧹 Обнаружен флаг очистки БД..."
    docker compose run --rm bot python cleanup_test_data.py
    if [ $? -eq 0 ]; then
        rm -f ".cleanup_db_on_deploy"
        echo "✅ БД очищена"
    fi
fi
```

### Способ B: Использовать deploy.sh

Изменить deploy.yml:

```yaml
script: |
  cd /home/git/fleet-live-bot
  chmod +x deploy.sh
  ./deploy.sh
```

## Диагностика кнопок

```bash
# Проверить кураторов в .env
cat .env | grep CURATOR_IDS

# Посмотреть логи проверки ролей
docker compose logs bot --tail 100 | grep "Role check"
```

## Полная документация

См. файл `ТЕХНИЧЕСКОЕ_ЗАДАНИЕ.md`
