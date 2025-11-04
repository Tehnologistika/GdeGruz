"""
Модуль для работы с базой данных рейсов.

Этот модуль обеспечивает управление рейсами и событиями рейсов.
"""

import aiosqlite
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging
import json

logger = logging.getLogger(__name__)
DB_PATH = Path("/home/user/GdeGruz/userdata/trips.db")


async def init_trips_db() -> None:
    """Инициализация БД рейсов. Создает таблицы и индексы."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        # Создать таблицу trips
        await db.execute("""
            CREATE TABLE IF NOT EXISTS trips (
                trip_id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_number TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                customer TEXT,
                carrier TEXT,
                loading_address TEXT,
                loading_date TEXT,
                loading_lat REAL,
                loading_lon REAL,
                unloading_address TEXT,
                unloading_date TEXT,
                unloading_lat REAL,
                unloading_lon REAL,
                cargo_type TEXT,
                rate REAL,
                status TEXT DEFAULT 'created',
                created_at TEXT NOT NULL,
                loading_confirmed_at TEXT,
                unloading_confirmed_at TEXT,
                completed_at TEXT,
                documents_sent TEXT,
                documents_received_at TEXT,
                curator_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES drivers(user_id)
            )
        """)

        # Создать таблицу trip_events
        await db.execute("""
            CREATE TABLE IF NOT EXISTS trip_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL,
                created_by INTEGER,
                metadata TEXT,
                FOREIGN KEY (trip_id) REFERENCES trips(trip_id)
            )
        """)

        # Создать индексы для trips
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_trips_user ON trips(user_id)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_trips_status ON trips(status)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_trips_number ON trips(trip_number)
        """)

        # Создать индексы для trip_events
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_trip_events_trip
            ON trip_events(trip_id, created_at DESC)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_trip_events_type ON trip_events(event_type)
        """)

        await db.commit()

    logger.info("Trips database initialized")


async def create_trip(
    trip_number: str,
    user_id: int,
    customer: str,
    carrier: str,
    loading_address: str,
    loading_date: str,
    unloading_address: str,
    unloading_date: str,
    cargo_type: str,
    rate: float,
    curator_id: Optional[int] = None
) -> int:
    """
    Создать новый рейс.

    Args:
        trip_number: Уникальный номер рейса
        user_id: Telegram ID водителя
        customer: Заказчик
        carrier: Перевозчик
        loading_address: Адрес погрузки
        loading_date: Дата погрузки (ISO формат)
        unloading_address: Адрес выгрузки
        unloading_date: Дата выгрузки (ISO формат)
        cargo_type: Тип груза
        rate: Ставка в рублях
        curator_id: ID куратора (опционально)

    Returns:
        int: ID созданного рейса

    Raises:
        sqlite3.IntegrityError: Если рейс с таким номером уже существует
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_schema(db)

        cursor = await db.execute("""
            INSERT INTO trips (
                trip_number, user_id, customer, carrier,
                loading_address, loading_date, unloading_address, unloading_date,
                cargo_type, rate, curator_id, created_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'created')
        """, (
            trip_number, user_id, customer, carrier,
            loading_address, loading_date, unloading_address, unloading_date,
            cargo_type, rate, curator_id, datetime.now().isoformat()
        ))

        trip_id = cursor.lastrowid
        await db.commit()

        # Логируем событие создания
        await log_trip_event(
            trip_id=trip_id,
            event_type="created",
            description=f"Рейс {trip_number} создан",
            created_by=curator_id
        )

    logger.info(f"Created trip #{trip_number} (ID: {trip_id}) for user {user_id}")
    return trip_id


async def get_trip(trip_id: int) -> Optional[Dict[str, Any]]:
    """
    Получить информацию о рейсе по ID.

    Args:
        trip_id: ID рейса

    Returns:
        Dict | None: Словарь с информацией о рейсе или None если не найден
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_schema(db)
        db.row_factory = aiosqlite.Row

        async with db.execute("""
            SELECT * FROM trips WHERE trip_id = ?
        """, (trip_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)

    return None


async def get_trip_by_number(trip_number: str) -> Optional[Dict[str, Any]]:
    """
    Получить информацию о рейсе по номеру.

    Args:
        trip_number: Номер рейса

    Returns:
        Dict | None: Словарь с информацией о рейсе или None если не найден
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_schema(db)
        db.row_factory = aiosqlite.Row

        async with db.execute("""
            SELECT * FROM trips WHERE trip_number = ?
        """, (trip_number,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)

    return None


async def get_user_active_trips(user_id: int) -> List[Dict[str, Any]]:
    """
    Получить активные рейсы водителя.

    Args:
        user_id: Telegram ID водителя

    Returns:
        List[Dict]: Список активных рейсов (не completed, не cancelled)
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_schema(db)
        db.row_factory = aiosqlite.Row

        async with db.execute("""
            SELECT * FROM trips
            WHERE user_id = ? AND status NOT IN ('completed', 'cancelled')
            ORDER BY created_at DESC
        """, (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_all_active_trips() -> List[Dict[str, Any]]:
    """
    Получить все активные рейсы для отчета куратора.

    Returns:
        List[Dict]: Список всех активных рейсов с информацией о водителях
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_schema(db)
        db.row_factory = aiosqlite.Row

        async with db.execute("""
            SELECT t.*, d.phone
            FROM trips t
            LEFT JOIN drivers d ON t.user_id = d.user_id
            WHERE t.status NOT IN ('completed', 'cancelled')
            ORDER BY t.loading_date
        """) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def update_trip_status(
    trip_id: int,
    status: str,
    user_id: Optional[int] = None
) -> None:
    """
    Обновить статус рейса.

    Args:
        trip_id: ID рейса
        status: Новый статус (created, loading, in_transit, unloading, completed, cancelled)
        user_id: ID пользователя, который меняет статус

    Автоматически устанавливает временные метки:
        - loading -> loading_confirmed_at
        - unloading -> unloading_confirmed_at
        - completed -> completed_at
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_schema(db)

        now = datetime.now().isoformat()

        # Определяем, какие дополнительные поля обновить
        updates = {"status": status}

        if status == "loading":
            updates["loading_confirmed_at"] = now
        elif status == "unloading":
            updates["unloading_confirmed_at"] = now
        elif status == "completed":
            updates["completed_at"] = now

        # Формируем SET часть запроса
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [trip_id]

        await db.execute(f"""
            UPDATE trips SET {set_clause} WHERE trip_id = ?
        """, values)
        await db.commit()

        # Логируем изменение статуса
        await log_trip_event(
            trip_id=trip_id,
            event_type="status_change",
            description=f"Статус изменён на: {status}",
            created_by=user_id,
            metadata={"old_status": None, "new_status": status}
        )

    logger.info(f"Trip {trip_id} status updated to {status}")


async def update_trip_documents_tracking(
    trip_id: int,
    tracking_number: Optional[str] = None,
    received: bool = False
) -> None:
    """
    Обновить информацию об отправке/получении документов.

    Args:
        trip_id: ID рейса
        tracking_number: Трек-номер СДЭК (если документы отправлены)
        received: True если документы получены в офисе
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_schema(db)

        if tracking_number:
            await db.execute("""
                UPDATE trips SET documents_sent = ? WHERE trip_id = ?
            """, (tracking_number, trip_id))

            await log_trip_event(
                trip_id=trip_id,
                event_type="documents_sent",
                description=f"Документы отправлены через СДЭК: {tracking_number}",
                metadata={"tracking_number": tracking_number}
            )

        if received:
            await db.execute("""
                UPDATE trips SET documents_received_at = ? WHERE trip_id = ?
            """, (datetime.now().isoformat(), trip_id))

            await log_trip_event(
                trip_id=trip_id,
                event_type="documents_received",
                description="Документы получены в офисе"
            )

        await db.commit()


async def log_trip_event(
    trip_id: int,
    event_type: str,
    description: str,
    created_by: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> int:
    """
    Логировать событие рейса.

    Args:
        trip_id: ID рейса
        event_type: Тип события (created, loading_start, status_change, etc.)
        description: Описание события
        created_by: ID пользователя, создавшего событие
        metadata: Дополнительные данные (будут сохранены как JSON)

    Returns:
        int: ID созданного события
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_schema(db)

        metadata_json = json.dumps(metadata) if metadata else None

        cursor = await db.execute("""
            INSERT INTO trip_events (trip_id, event_type, description, created_at, created_by, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            trip_id,
            event_type,
            description,
            datetime.now().isoformat(),
            created_by,
            metadata_json
        ))

        event_id = cursor.lastrowid
        await db.commit()

    logger.info(f"Logged event '{event_type}' for trip {trip_id}")
    return event_id


async def get_trip_events(trip_id: int) -> List[Dict[str, Any]]:
    """
    Получить историю событий рейса.

    Args:
        trip_id: ID рейса

    Returns:
        List[Dict]: Список событий в хронологическом порядке
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_schema(db)
        db.row_factory = aiosqlite.Row

        async with db.execute("""
            SELECT * FROM trip_events
            WHERE trip_id = ?
            ORDER BY created_at ASC
        """, (trip_id,)) as cursor:
            rows = await cursor.fetchall()
            events = []
            for row in rows:
                event = dict(row)
                # Распарсить JSON metadata
                if event['metadata']:
                    try:
                        event['metadata'] = json.loads(event['metadata'])
                    except:
                        pass
                events.append(event)
            return events


async def _ensure_schema(db: aiosqlite.Connection) -> None:
    """Вспомогательная функция для обеспечения наличия схемы БД."""
    # Проверить, что таблицы существуют
    cursor = await db.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name IN ('trips', 'trip_events')
    """)
    tables = await cursor.fetchall()

    if len(tables) < 2:
        # Пере-инициализируем БД если таблиц нет
        logger.warning("Trips database tables not found, re-initializing...")
        await init_trips_db()
