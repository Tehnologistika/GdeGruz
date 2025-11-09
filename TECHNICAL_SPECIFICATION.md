# Техническое задание: Удаление тестовых рейсов из БД GdeGruz Bot

## Дата создания: 2025-11-09

## 1. ОПИСАНИЕ ПРОБЛЕМЫ

### 1.1 Симптомы

После деплоя с попыткой очистки базы данных:

1. **В меню "Все рейсы" (куратор) остались тестовые рейсы**
   - При нажатии кнопки "📊 Все рейсы" в админ-панели куратора показываются старые тестовые рейсы
   - Эти рейсы не должны отображаться

2. **Появились нежелательные кнопки клавиатуры**
   - После деплоя появились кнопки, которые ранее были убраны
   - Точно неизвестно какие именно кнопки (требуется диагностика)

### 1.2 Причина

Скрипты очистки БД (`cleanup_test_data.py` и `urgent_cleanup.py`) НЕ выполнились успешно на продакшн-сервере при деплое.

Возможные причины:
- Неправильный путь к БД в Docker-контейнере
- Скрипт запустился до монтирования volume с БД
- Скрипт завершился с ошибкой, но деплой продолжился
- Флаг `.cleanup_db_on_deploy` был удален до фактической очистки

---

## 2. АРХИТЕКТУРА ПРОЕКТА

### 2.1 Общая структура

```
GdeGruz/
├── bot/                    # Telegram бот (Aiogram 3.0.0)
│   ├── main.py            # Точка входа бота
│   ├── keyboards.py       # Определения клавиатур
│   ├── utils.py           # Вспомогательные функции (is_curator)
│   └── handlers/          # Обработчики событий
│       ├── start.py       # /start - выдача клавиатур по ролям
│       ├── contact.py     # Регистрация по номеру телефона
│       ├── curator.py     # Панель управления кураторов
│       ├── driver_trips.py # Рейсы водителей
│       ├── location.py    # Обработка геолокации
│       ├── documents.py   # Загрузка документов
│       └── ...
├── web/                    # FastAPI веб-API
│   └── api.py             # HTTP API для карты
├── db.py                  # Работа с points.db (drivers, points)
├── db_trips.py            # Работа с trips.db (trips, trip_events)
├── db_documents.py        # Работа с documents.db
├── cleanup_test_data.py   # АСИНХРОННЫЙ скрипт очистки БД
├── urgent_cleanup.py      # СИНХРОННЫЙ скрипт очистки БД (fallback)
├── deploy.sh              # Скрипт деплоя на сервере
├── docker-compose.yml     # Конфигурация Docker
├── Dockerfile             # Сборка образа
└── .github/workflows/
    └── deploy.yml         # GitHub Actions - автодеплой

```

### 2.2 База данных SQLite

Проект использует **3 отдельных БД SQLite**:

#### **points.db** (местоположение водителей)

```sql
-- Таблица водителей
CREATE TABLE drivers (
    user_id INTEGER PRIMARY KEY,
    phone   TEXT,
    active  INTEGER NOT NULL DEFAULT 1   -- 1 = отслеживание включено
);

-- Таблица координат
CREATE TABLE points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    ts TEXT NOT NULL                      -- ISO timestamp
);
```

**Путь в Docker**: `/app/data/points.db`

#### **trips.db** (рейсы)

```sql
-- Таблица рейсов
CREATE TABLE trips (
    trip_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_number TEXT UNIQUE NOT NULL,     -- ТЛ-0001, ТЛ-0002, ...
    user_id INTEGER,                      -- Telegram ID водителя (NULL до регистрации)
    phone TEXT NOT NULL,                  -- +79991234567
    loading_address TEXT NOT NULL,        -- Адрес погрузки
    loading_date TEXT NOT NULL,           -- ДД.ММ.ГГГГ
    unloading_address TEXT NOT NULL,      -- Адрес выгрузки
    unloading_date TEXT NOT NULL,         -- ДД.ММ.ГГГГ
    rate REAL NOT NULL,                   -- Ставка в рублях
    status TEXT DEFAULT 'assigned',       -- assigned/active/in_transit/delivered/completed/cancelled
    created_at TEXT NOT NULL,             -- ISO timestamp создания
    loading_confirmed_at TEXT,            -- Время подтверждения погрузки
    unloading_confirmed_at TEXT,          -- Время подтверждения выгрузки
    completed_at TEXT,                    -- Время завершения
    curator_id INTEGER,                   -- ID куратора, создавшего рейс
    sdek_tracking TEXT                    -- Трек-номер СДЭК
);

-- Таблица событий рейсов
CREATE TABLE trip_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,             -- created/activated/status_changed/completed
    description TEXT,                     -- Описание события
    created_at TEXT NOT NULL,             -- ISO timestamp
    created_by INTEGER,                   -- user_id инициатора
    metadata TEXT,                        -- JSON с доп. данными
    FOREIGN KEY (trip_id) REFERENCES trips(trip_id)
);
```

**Путь в Docker**: `/app/data/trips.db`

#### **documents.db** (документы)

```sql
CREATE TABLE documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    document_type TEXT NOT NULL,          -- loading_photo/acceptance_act/unloading_photo/invoice
    file_id TEXT NOT NULL,                -- Telegram file_id
    uploaded_at TEXT NOT NULL,            -- ISO timestamp
    FOREIGN KEY (trip_id) REFERENCES trips(trip_id)
);
```

**Путь в Docker**: `/app/data/documents.db`

### 2.3 Deployment Flow

```
┌──────────────────────────────────────────────────────────┐
│ 1. Developer pushes to branch claude/review-*           │
│    (или merge в main через PR)                          │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────┐
│ 2. GitHub Actions (.github/workflows/deploy.yml)        │
│    • Triggered on push to main                          │
│    • SSH to Timeweb server                              │
│    • cd /home/git/fleet-live-bot                        │
│    • git pull origin main                               │
│    • docker-compose down                                │
│    • docker-compose up -d --build                       │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────┐
│ 3. Docker Compose (docker-compose.yml)                  │
│    • Service: bot  (STAGE=bot)                          │
│    • Service: web  (STAGE=web, port 8000)               │
│    • Volume: ./data:/app/data (ПЕРСИСТЕНТНОЕ ХРАНИЛИЩЕ) │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────┐
│ 4. Dockerfile (multi-stage build)                       │
│    • Builder: установка dependencies                    │
│    • Runtime: копирование приложения                    │
│    • CMD: if STAGE=bot → python -m bot.main             │
│           if STAGE=web → uvicorn web.api:app            │
└──────────────────────────────────────────────────────────┘
```

**ВАЖНО**: Deploy.yml НЕ использует deploy.sh!

- `.github/workflows/deploy.yml` выполняет деплой НАПРЯМУЮ через SSH
- `deploy.sh` существует, но НЕ ВЫЗЫВАЕТСЯ из GitHub Actions
- Флаг `.cleanup_db_on_deploy` проверяется в `deploy.sh`, но deploy.sh НЕ ЗАПУСКАЕТСЯ!

**Это КРИТИЧЕСКАЯ проблема**: deploy.yml не проверяет флаг очистки БД!

### 2.4 Система ролей

Проект различает **2 роли пользователей**:

#### Куратор (Dispatcher/Manager)

**Определение**: `user_id в CURATOR_IDS` (из .env)

**Функция проверки**: `bot/utils.py::is_curator(user_id)`

**Клавиатура**: `curator_kb()` из `bot/keyboards.py`
- 🎛 Панель управления
- ➕ Создать рейс
- 📋 Список рейсов
- 📊 Статистика

**Функционал**:
- Создание рейсов через /create_trip
- Просмотр всех рейсов (/trips, callback: list_trips)
- Активация рейсов вручную
- Завершение рейсов
- Отмена рейсов
- Запрос местоположения у водителя
- Просмотр статистики

#### Водитель (Driver)

**Определение**: `user_id НЕ в CURATOR_IDS`

**Клавиатура**: `location_kb()` из `bot/keyboards.py`
- 📍 Поделиться местоположением
- 📤 Отправить документы
- 📋 Мой рейс
- ❓ Помощь
- 🛑 Закончить отслеживание

**Функционал**:
- Регистрация по номеру телефона
- Отправка геолокации
- Просмотр своих рейсов
- Изменение статуса своего рейса
- Загрузка документов

---

## 3. КОД ПРОБЛЕМНЫХ УЧАСТКОВ

### 3.1 Меню "Все рейсы" (bot/handlers/curator.py)

```python
@router.callback_query(F.data == "list_trips")
async def list_trips_callback(callback: CallbackQuery):
    """Показать список всех рейсов."""
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    try:
        # ЗДЕСЬ ПРОБЛЕМА: Получаем ВСЕ рейсы без фильтрации
        all_trips = await db_trips.get_all_trips(limit=50)  # <-- строка 1107

        if not all_trips:
            # Если рейсов нет - OK
            ...
            return

        # Формируем список (строка 1125-1146)
        text = "📊 <b>Все рейсы</b> (последние 10):\n\n"

        for trip in all_trips[:10]:
            emoji = status_emoji.get(trip['status'], '❓')
            text += (
                f"{emoji} <b>{trip['trip_number']}</b> - {trip['phone']}\n"
                f"   {trip['loading_address'][:30]}...\n"
                f"   ↓\n"
                f"   {trip['unloading_address'][:30]}...\n\n"
            )
        # ...
```

**Функция получения рейсов** (db_trips.py:436-472):

```python
async def get_all_trips(
    status: Optional[str] = None,
    curator_id: Optional[int] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Получить все рейсы с фильтрацией.
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_schema(conn)
        conn.row_factory = aiosqlite.Row

        query = "SELECT * FROM trips WHERE 1=1"  # <-- БЕЗ ФИЛЬТРОВ ПО УМОЛЧАНИЮ
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)

        if curator_id:
            query += " AND curator_id = ?"
            params.append(curator_id)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        async with conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
```

**Вызов**: `list_trips_callback` вызывает `get_all_trips(limit=50)` БЕЗ параметра `status`, поэтому возвращает ВСЕ рейсы из БД, включая тестовые.

### 3.2 Скрипты очистки БД

#### cleanup_test_data.py (АСИНХРОННЫЙ)

```python
# Поиск пути к БД
def find_db_path(db_name: str) -> Path:
    """Находит путь к базе данных."""
    possible_paths = [
        DATA_DIR / db_name,              # ./data/trips.db
        BASE_DIR / db_name,              # ./trips.db
        Path("/app/data") / db_name,     # Docker: /app/data/trips.db
        Path("/app") / db_name,          # Docker: /app/trips.db
    ]

    for path in possible_paths:
        if path.exists():
            logger.info(f"✅ Найдена БД: {path}")
            return path

    # Возвращаем путь по умолчанию
    logger.warning(f"⚠️ БД {db_name} не найдена, используется путь по умолчанию: {DATA_DIR / db_name}")
    return DATA_DIR / db_name

TRIPS_DB = find_db_path("trips.db")

async def cleanup_trips():
    """Очистка всех рейсов."""
    if not TRIPS_DB.exists():
        logger.warning(f"База данных {TRIPS_DB} не найдена, пропускаем")
        return 0

    async with aiosqlite.connect(TRIPS_DB) as db:
        # Подсчитываем количество рейсов
        async with db.execute("SELECT COUNT(*) FROM trips") as cursor:
            count = (await cursor.fetchone())[0]

        # ...статистика...

        # УДАЛЯЕМ ВСЕ РЕЙСЫ
        await db.execute("DELETE FROM trips")  # <-- строка 86

        # Очищаем события
        try:
            await db.execute("DELETE FROM trip_events")  # <-- строка 95
        except:
            pass

        # Сбрасываем автоинкремент
        try:
            await db.execute("DELETE FROM sqlite_sequence WHERE name='trips'")
        except:
            pass

        await db.commit()
```

#### urgent_cleanup.py (СИНХРОННЫЙ - fallback)

```python
def cleanup():
    # Поиск БД
    possible_paths = [
        Path("data/trips.db"),
        Path("trips.db"),
        Path("/app/data/trips.db"),
        Path("/app/trips.db"),
    ]

    db_path = None
    for p in possible_paths:
        if p.exists():
            db_path = p
            print(f"✅ Найдена БД: {db_path}")
            break

    if not db_path:
        print("❌ База данных trips.db не найдена!")
        return False

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Считаем рейсы
        cursor.execute("SELECT COUNT(*) FROM trips")
        count = cursor.fetchone()[0]

        # УДАЛЯЕМ ВСЕ
        cursor.execute("DELETE FROM trips")
        cursor.execute("DELETE FROM trip_events")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='trips'")

        conn.commit()
        conn.close()

        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
```

### 3.3 Deploy процесс

#### .github/workflows/deploy.yml

```yaml
name: Auto Deploy Bot

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
    - name: Deploy to Timeweb Server
      uses: appleboy/ssh-action@v0.1.5
      with:
        host: ${{ secrets.HOST }}
        username: ${{ secrets.USERNAME }}
        key: ${{ secrets.SSH_KEY }}
        script: |
          cd /home/git/fleet-live-bot

          git pull origin main

          docker-compose down
          docker-compose up -d --build

          docker-compose ps

          echo "Деплой завершён успешно"

          echo "✅ Деплой завершён!"

          exit 0
```

**ПРОБЛЕМА**: deploy.yml НЕ проверяет флаг `.cleanup_db_on_deploy`!

#### deploy.sh (НЕ ИСПОЛЬЗУЕТСЯ!)

```bash
#!/bin/sh
PROJECT_DIR="${PROJECT_DIR:-/home/git/fleet-live-bot}"

cd "$PROJECT_DIR" || exit 1

echo "🔄 Pulling latest changes from main..."
git pull origin main

# ПРОВЕРКА ФЛАГА ОЧИСТКИ
if [ -f ".cleanup_db_on_deploy" ]; then
    echo "🧹 Обнаружен флаг очистки БД..."

    # Запуск через Docker
    docker compose run --rm bot python cleanup_test_data.py

    # Удаление флага
    if [ $? -eq 0 ]; then
        rm -f ".cleanup_db_on_deploy"
        echo "✅ База данных очищена, флаг удален"
    else
        echo "❌ Ошибка при очистке"
    fi
fi

echo "🐳 Building and starting containers..."
docker compose pull
docker compose up -d --build

echo "✅ Deployment completed!"
```

**ПРОБЛЕМА**: Этот скрипт существует, но НЕ ВЫЗЫВАЕТСЯ из deploy.yml!

### 3.4 Клавиатуры (bot/keyboards.py)

```python
def main_kb() -> ReplyKeyboardMarkup:
    """
    Главная клавиатура бота (при старте).
    ИСПОЛЬЗУЕТСЯ ТОЛЬКО ПРИ ПЕРВОМ ЗАПУСКЕ для запроса номера телефона.
    """
    kb = ReplyKeyboardBuilder()
    kb.button(text="📱 Поделиться номером", request_contact=True)
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)


def location_kb() -> ReplyKeyboardMarkup:
    """
    Клавиатура после регистрации водителя.
    ОСНОВНАЯ КЛАВИАТУРА для повседневной работы.
    """
    kb = ReplyKeyboardBuilder()
    kb.button(text="📍 Поделиться местоположением", request_location=True)
    kb.button(text="📤 Отправить документы")
    kb.button(text="📋 Мой рейс")
    kb.button(text="❓ Помощь")
    kb.button(text="🛑 Закончить отслеживание")
    kb.adjust(1, 2, 1, 1)
    return kb.as_markup(resize_keyboard=True)


def curator_kb() -> ReplyKeyboardMarkup:
    """
    Клавиатура для куратора рейсов.
    Содержит кнопки управления рейсами вместо команд.
    """
    kb = ReplyKeyboardBuilder()
    kb.button(text="🎛 Панель управления")
    kb.button(text="➕ Создать рейс")
    kb.button(text="📋 Список рейсов")
    kb.button(text="📊 Статистика")
    kb.adjust(2, 2)
    return kb.as_markup(resize_keyboard=True)


def resume_kb() -> ReplyKeyboardMarkup:
    """Клавиатура для возобновления отслеживания."""
    kb = ReplyKeyboardBuilder()
    kb.button(text="Возобновить отслеживание")
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)
```

**Где выдаются клавиатуры**:

1. **start.py**: /start
   - Куратор → `curator_kb()`
   - Водитель → `main_kb()`

2. **contact.py**: Регистрация по номеру
   - Куратор → `curator_kb()`
   - Водитель → `location_kb()`

3. **driver_trips.py**: После активации рейса
   - Водитель → `location_kb()`

---

## 4. ДИАГНОСТИКА ПРОБЛЕМЫ

### 4.1 Почему рейсы не удалились?

**Гипотезы**:

1. **GitHub Actions не запускает cleanup скрипт**
   - ✅ ПОДТВЕРЖДЕНО: deploy.yml НЕ проверяет `.cleanup_db_on_deploy`
   - deploy.yml НЕ вызывает deploy.sh
   - Флаг создан, но никогда не обрабатывается

2. **Путь к БД неправильный в Docker**
   - Docker volume: `./data:/app/data`
   - Скрипт ищет: `/app/data/trips.db`
   - Должно работать, НО скрипт может запуститься ДО монтирования volume

3. **Скрипт не имеет прав на запись**
   - Маловероятно, т.к. бот работает с БД нормально

4. **Скрипт завершился с ошибкой**
   - Нет логов выполнения скрипта

### 4.2 Проверочные шаги

**На сервере** (SSH: username@host):

```bash
# 1. Проверить наличие БД
cd /home/git/fleet-live-bot
ls -lah data/trips.db

# 2. Открыть БД и посмотреть рейсы
sqlite3 data/trips.db "SELECT trip_number, status, created_at FROM trips ORDER BY created_at DESC;"

# 3. Посмотреть количество рейсов
sqlite3 data/trips.db "SELECT COUNT(*) FROM trips;"

# 4. Проверить permissions
ls -lah data/

# 5. Проверить работает ли Docker volume
docker compose exec bot ls -lah /app/data/

# 6. Запустить cleanup вручную
docker compose run --rm bot python cleanup_test_data.py

# 7. Или запустить синхронный cleanup
docker compose run --rm bot python urgent_cleanup.py
```

---

## 5. РЕШЕНИЕ ПРОБЛЕМЫ

### 5.1 Краткосрочное решение (Hotfix)

**Вручную очистить БД на сервере**:

```bash
# SSH на сервер
ssh username@host

# Перейти в проект
cd /home/git/fleet-live-bot

# Вариант 1: Через Docker (предпочтительно)
docker compose run --rm bot python urgent_cleanup.py

# Вариант 2: Напрямую через sqlite3
sqlite3 data/trips.db "DELETE FROM trips;"
sqlite3 data/trips.db "DELETE FROM trip_events;"
sqlite3 data/trips.db "DELETE FROM sqlite_sequence WHERE name='trips';"

# Вариант 3: Если БД повреждена - удалить полностью
docker compose down
rm -f data/trips.db
docker compose up -d
# Бот создаст новую БД при запуске
```

### 5.2 Долгосрочное решение (Правильный fix)

**Изменить deploy.yml для поддержки очистки БД**:

```yaml
name: Auto Deploy Bot

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
    - name: Deploy to Timeweb Server
      uses: appleboy/ssh-action@v0.1.5
      with:
        host: ${{ secrets.HOST }}
        username: ${{ secrets.USERNAME }}
        key: ${{ secrets.SSH_KEY }}
        script: |
          cd /home/git/fleet-live-bot

          git pull origin main

          # НОВОЕ: Проверка флага очистки БД
          if [ -f ".cleanup_db_on_deploy" ]; then
              echo "🧹 Обнаружен флаг очистки БД..."

              # Запускаем cleanup через Docker
              docker compose run --rm bot python cleanup_test_data.py

              # Проверяем результат
              if [ $? -eq 0 ]; then
                  rm -f ".cleanup_db_on_deploy"
                  echo "✅ БД очищена, флаг удален"
              else
                  echo "❌ Ошибка очистки БД"
                  exit 1
              fi
          fi

          docker-compose down
          docker-compose up -d --build

          docker-compose ps

          echo "✅ Деплой завершён!"
```

**ИЛИ использовать deploy.sh**:

```yaml
script: |
  cd /home/git/fleet-live-bot
  chmod +x deploy.sh
  ./deploy.sh
```

### 5.3 Проверка проблемы с кнопками

**Возможные причины**:

1. **Куратору показывается `location_kb()` вместо `curator_kb()`**
   - Проверить логи: `bot.utils.is_curator()` должен логировать проверку роли
   - Проверить `.env` на сервере: `CURATOR_IDS` должен содержать правильные ID

2. **Водителю показывается `curator_kb()` вместо `location_kb()`**
   - Водитель случайно добавлен в `CURATOR_IDS`

3. **Показывается `resume_kb()` вместо основной клавиатуры**
   - Проверить handlers/resume.py и handlers/stop.py

**Диагностика на сервере**:

```bash
# Проверить .env
cat /home/git/fleet-live-bot/.env | grep CURATOR_IDS

# Посмотреть логи бота
docker compose logs bot --tail 100 | grep "Role check"

# Проверить конкретного пользователя
docker compose logs bot | grep "user_id=5799866832"
```

---

## 6. ТЕХНИЧЕСКИЕ ДЕТАЛИ ДЛЯ ОТЛАДКИ

### 6.1 Подключение к серверу

```bash
# SSH credentials хранятся в GitHub Secrets:
# - HOST: адрес сервера
# - USERNAME: имя пользователя
# - SSH_KEY: приватный ключ

ssh username@host

# Директория проекта:
cd /home/git/fleet-live-bot
```

### 6.2 Docker команды

```bash
# Просмотр логов
docker compose logs bot --tail 100 -f
docker compose logs web --tail 100 -f

# Перезапуск
docker compose restart bot
docker compose restart web

# Полный перебилд
docker compose down
docker compose up -d --build

# Запуск команды в контейнере
docker compose exec bot python -c "import db; print(db.DB_PATH)"
docker compose exec bot ls -lah /app/data/

# Запуск one-off контейнера
docker compose run --rm bot python cleanup_test_data.py
docker compose run --rm bot python urgent_cleanup.py

# Проверка volume
docker volume ls
docker volume inspect fleet-live-bot_data  # если используется named volume
```

### 6.3 Логирование

**Уровни логов** (bot/main.py:45-48):

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
```

**Важные логи для отладки**:

```
# Проверка роли
bot.utils - INFO - Role check: user_id=123, CURATOR_IDS='5799866832,6835069941', parsed_ids=[5799866832, 6835069941], is_curator=False

# Сохранение телефона
db - INFO - Phone saved: user_id=123 -> phone=+79991234567

# Регистрация водителя
bot.handlers.contact - INFO - Contact received: user_id=123, name=Ivan Ivanov, phone=+79991234567
bot.handlers.contact - INFO - User 123 is DRIVER - checking for assigned trips
bot.handlers.contact - INFO - Found 0 assigned trips for phone +79991234567

# Создание рейса
db_trips - INFO - Created trip #ТЛ-0001 for phone +79991234567

# Очистка БД
cleanup_test_data - INFO - ✅ Найдена БД: /app/data/trips.db
cleanup_test_data - INFO - 🔍 Найдено рейсов: 5
cleanup_test_data - INFO - ✅ Успешно удалено 5 рейсов из /app/data/trips.db
```

### 6.4 Переменные окружения (.env)

```bash
# Обязательные
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
ADMIN_ID=123456789
GROUP_CHAT_ID=-1001234567890
DOCUMENTS_GROUP_ID=-1001234567890
CURATOR_IDS=5799866832,6835069941

# Опциональные
REMIND_HOURS=0.2
TIMEZONE=Europe/Berlin
API_SECRET_TOKEN=your_secret_token_here
```

**Проверка на сервере**:

```bash
# Посмотреть все переменные
docker compose exec bot env | grep -E "BOT_TOKEN|CURATOR_IDS|GROUP_CHAT_ID"

# Проверить конкретную переменную
docker compose exec bot printenv CURATOR_IDS
```

---

## 7. ПЛАН ВЫПОЛНЕНИЯ ЗАДАЧИ

### Этап 1: Диагностика текущего состояния

1. **SSH на сервер**
   ```bash
   ssh username@host
   cd /home/git/fleet-live-bot
   ```

2. **Проверить количество рейсов в БД**
   ```bash
   sqlite3 data/trips.db "SELECT COUNT(*) FROM trips;"
   sqlite3 data/trips.db "SELECT trip_number, status, phone, created_at FROM trips ORDER BY created_at DESC LIMIT 10;"
   ```

3. **Проверить логи бота**
   ```bash
   docker compose logs bot --tail 200 | grep -E "Role check|CURATOR|DRIVER"
   ```

4. **Проверить .env**
   ```bash
   cat .env | grep CURATOR_IDS
   ```

5. **Документировать находки**
   - Сколько рейсов в БД?
   - Какие статусы?
   - Кто куратор (user_id)?
   - Проблема с кнопками подтверждена?

### Этап 2: Очистка БД

1. **Вариант A: Через cleanup скрипт**
   ```bash
   docker compose run --rm bot python cleanup_test_data.py
   ```

2. **Вариант B: Напрямую SQL**
   ```bash
   sqlite3 data/trips.db "DELETE FROM trips;"
   sqlite3 data/trips.db "DELETE FROM trip_events;"
   sqlite3 data/trips.db "DELETE FROM sqlite_sequence WHERE name='trips';"
   ```

3. **Проверка**
   ```bash
   sqlite3 data/trips.db "SELECT COUNT(*) FROM trips;"
   # Должно быть: 0
   ```

### Этап 3: Исправление деплоя

1. **Обновить .github/workflows/deploy.yml**
   - Добавить проверку флага `.cleanup_db_on_deploy`
   - Добавить запуск cleanup скрипта при наличии флага

2. **Протестировать**
   - Создать флаг: `touch .cleanup_db_on_deploy`
   - Commit & push
   - Проверить, что cleanup выполнился

### Этап 4: Исправление проблемы с кнопками

1. **Если проблема в роли**:
   - Проверить `CURATOR_IDS` в .env
   - Убедиться что `bot/utils.py::is_curator()` работает правильно

2. **Если проблема в коде**:
   - Найти где выдается неправильная клавиатура
   - Исправить логику в handlers

### Этап 5: Тестирование

1. **Создать тестовый рейс**
   - Войти как куратор
   - Создать рейс через /create_trip

2. **Проверить меню "Все рейсы"**
   - Должен показываться только что созданный рейс

3. **Проверить клавиатуры**
   - Куратор: `curator_kb()`
   - Водитель: `location_kb()`

4. **Очистить БД снова**
   - Создать флаг `.cleanup_db_on_deploy`
   - Push в main
   - Проверить что БД очистилась автоматически

---

## 8. ДОПОЛНИТЕЛЬНЫЕ РЕКОМЕНДАЦИИ

### 8.1 Мониторинг

Добавить health checks для проверки состояния БД:

```python
# bot/main.py
async def health_check():
    """Проверка здоровья системы."""
    async with aiosqlite.connect(db_trips.DB_PATH) as conn:
        async with conn.execute("SELECT COUNT(*) FROM trips") as cursor:
            count = (await cursor.fetchone())[0]
            logger.info(f"Health check: {count} trips in database")
```

### 8.2 Backup БД

Добавить в deploy.sh backup перед очисткой:

```bash
if [ -f ".cleanup_db_on_deploy" ]; then
    echo "📦 Creating backup..."
    timestamp=$(date +%Y%m%d_%H%M%S)
    cp data/trips.db "data/backups/trips_${timestamp}.db"

    echo "🧹 Cleaning database..."
    docker compose run --rm bot python cleanup_test_data.py
fi
```

### 8.3 Улучшение cleanup скрипта

Добавить dry-run режим:

```python
# cleanup_test_data.py
import sys

DRY_RUN = "--dry-run" in sys.argv

async def cleanup_trips():
    if DRY_RUN:
        logger.info("DRY RUN: Would delete %d trips", count)
        return 0

    # Actual deletion
    await db.execute("DELETE FROM trips")
```

---

## 9. КОНТАКТЫ И ССЫЛКИ

### Документация проекта

- GitHub: `Tehnologistika/GdeGruz`
- Branch для разработки: `claude/review-gdegruz-bot-*`
- Main branch: `main`

### Технологии

- Python: 3.11
- Aiogram: 3.0.0
- FastAPI: latest
- SQLite: 3.x
- Docker: latest
- Docker Compose: v3.9

### Полезные команды

```bash
# Просмотр структуры БД
sqlite3 data/trips.db ".schema trips"
sqlite3 data/trips.db ".schema trip_events"

# Export БД в SQL
sqlite3 data/trips.db .dump > backup.sql

# Import БД из SQL
sqlite3 new_trips.db < backup.sql

# Проверка целостности БД
sqlite3 data/trips.db "PRAGMA integrity_check;"

# Vacuum БД (очистка неиспользуемого пространства)
sqlite3 data/trips.db "VACUUM;"
```

---

## 10. ЗАКЛЮЧЕНИЕ

**Основная проблема**: `.github/workflows/deploy.yml` НЕ проверяет флаг `.cleanup_db_on_deploy` и НЕ запускает cleanup скрипт.

**Решение**: Обновить deploy.yml для поддержки автоматической очистки БД при наличии флага.

**Альтернатива**: Переключиться на использование `deploy.sh` который уже имеет эту логику.

**Быстрый fix**: Вручную запустить cleanup на сервере через SSH.

---

**Создано**: 2025-11-09
**Автор**: Claude Code (Anthropic)
**Для**: Новая сессия Claude Code
**Цель**: Удаление тестовых рейсов из БД и исправление проблемы с деплоем
