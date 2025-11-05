"""
Модуль для работы с рейсами в БД.

Упрощенная система управления рейсами:
- Работа по телефону водителя
- Минимальные данные (телефон, адреса, даты, ставка)
- Статусы: assigned, active, loading, in_transit, unloading, completed
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import aiosqlite

logger = logging.getLogger(__name__)

# Import phone normalization function
from db import normalize_phone

DB_PATH = Path("/home/git/fleet-live-bot/userdata/trips.db")


async def init() -> None:
    """Инициализация БД рейсов."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_schema(db)


async def _ensure_schema(db: aiosqlite.Connection) -> None:
    """Создать/обновить схему БД рейсов."""

    # Создать таблицу trips с полем phone
    await db.execute("""
        CREATE TABLE IF NOT EXISTS trips (
            trip_id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_number TEXT UNIQUE NOT NULL,
            user_id INTEGER,
            phone TEXT NOT NULL,
            loading_address TEXT NOT NULL,
            loading_date TEXT NOT NULL,
            unloading_address TEXT NOT NULL,
            unloading_date TEXT NOT NULL,
            rate REAL NOT NULL,
            status TEXT DEFAULT 'assigned',
            created_at TEXT NOT NULL,
            loading_confirmed_at TEXT,
            unloading_confirmed_at TEXT,
            completed_at TEXT,
            curator_id INTEGER
        )
    """)

    # Создать индекс по телефону
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_trips_phone ON trips(phone)
    """)

    # Создать индекс по user_id
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_trips_user ON trips(user_id)
    """)

    # Создать индекс по статусу
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_trips_status ON trips(status)
    """)

    # Создать индекс по номеру
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_trips_number ON trips(trip_number)
    """)

    # Таблица trip_events остается без изменений
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

    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_trip_events_trip
        ON trip_events(trip_id, created_at DESC)
    """)

    await db.commit()


async def _generate_trip_number() -> str:
    """
    Генерация уникального номера рейса в формате ТЛ-XXXX.

    Returns:
        str: Номер рейса (например: ТЛ-0001, ТЛ-0042)
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_schema(conn)

        # Найти максимальный номер
        async with conn.execute("""
            SELECT trip_number FROM trips
            WHERE trip_number LIKE 'ТЛ-%'
            ORDER BY trip_number DESC LIMIT 1
        """) as cursor:
            row = await cursor.fetchone()

        if row:
            # Извлечь число из "ТЛ-0042"
            last_num = int(row[0].split('-')[1])
            new_num = last_num + 1
        else:
            new_num = 1

        return f"ТЛ-{new_num:04d}"  # ТЛ-0001, ТЛ-0002, ...


async def create_trip_by_curator(
    phone: str,
    loading_address: str,
    loading_date: str,
    unloading_address: str,
    unloading_date: str,
    rate: float,
    curator_id: int
) -> tuple[int, str]:
    """
    Создать рейс куратором.

    Args:
        phone: Телефон водителя (+79991234567)
        loading_address: Адрес погрузки
        loading_date: Дата погрузки (ДД.ММ.ГГГГ)
        unloading_address: Адрес выгрузки
        unloading_date: Дата выгрузки (ДД.ММ.ГГГГ)
        rate: Ставка в рублях
        curator_id: Telegram ID куратора

    Returns:
        tuple[int, str]: (trip_id, trip_number)
    """
    # Нормализуем телефон
    phone = normalize_phone(phone)

    # Генерируем уникальный номер рейса
    trip_number = await _generate_trip_number()

    # Получаем user_id по телефону (если водитель уже в системе)
    import db
    user_id = await db.get_user_id_by_phone(phone)

    # Если водитель не найден, ставим 0 (обновится при регистрации)
    if not user_id:
        user_id = 0

    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_schema(conn)

        cursor = await conn.execute("""
            INSERT INTO trips (
                trip_number, user_id, phone,
                loading_address, loading_date,
                unloading_address, unloading_date,
                rate, curator_id, created_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'assigned')
        """, (
            trip_number, user_id, phone,
            loading_address, loading_date,
            unloading_address, unloading_date,
            rate, curator_id, datetime.now().isoformat()
        ))

        trip_id = cursor.lastrowid
        await conn.commit()

        # Логируем событие создания
        await log_trip_event(
            trip_id=trip_id,
            event_type="created",
            description=f"Рейс создан куратором",
            created_by=curator_id
        )

    logger.info(f"Created trip #{trip_number} for phone {phone}")
    return trip_id, trip_number


async def get_trips_by_phone(phone: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Получить рейсы по телефону водителя.

    Args:
        phone: Телефон водителя
        status: Фильтр по статусу (опционально)

    Returns:
        List[Dict]: Список рейсов
    """
    # Нормализуем телефон
    phone = normalize_phone(phone)

    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_schema(conn)
        conn.row_factory = aiosqlite.Row

        if status:
            query = """
                SELECT * FROM trips
                WHERE phone = ? AND status = ?
                ORDER BY created_at DESC
            """
            params = (phone, status)
        else:
            query = """
                SELECT * FROM trips
                WHERE phone = ?
                ORDER BY created_at DESC
            """
            params = (phone,)

        async with conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_trip(trip_id: int) -> Optional[Dict[str, Any]]:
    """
    Получить рейс по ID.

    Args:
        trip_id: ID рейса

    Returns:
        Dict | None: Данные рейса или None
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_schema(conn)
        conn.row_factory = aiosqlite.Row

        async with conn.execute("""
            SELECT * FROM trips WHERE trip_id = ?
        """, (trip_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_user_active_trips(user_id: int) -> List[Dict[str, Any]]:
    """
    Получить активные рейсы водителя.

    Args:
        user_id: Telegram user_id

    Returns:
        List[Dict]: Список активных рейсов
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_schema(conn)
        conn.row_factory = aiosqlite.Row

        async with conn.execute("""
            SELECT * FROM trips
            WHERE user_id = ? AND status NOT IN ('completed', 'cancelled')
            ORDER BY created_at DESC
        """, (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def update_trip_user_id(trip_id: int, user_id: int) -> None:
    """
    Обновить user_id рейса (когда водитель регистрируется).

    Args:
        trip_id: ID рейса
        user_id: Telegram user_id водителя
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_schema(conn)

        await conn.execute("""
            UPDATE trips SET user_id = ? WHERE trip_id = ?
        """, (user_id, trip_id))

        await conn.commit()

    logger.info(f"Updated trip {trip_id} user_id to {user_id}")


async def activate_trip(trip_id: int, activated_by: Optional[int] = None) -> None:
    """
    Активировать рейс (водителем или куратором).

    Args:
        trip_id: ID рейса
        activated_by: Кто активировал (user_id)
    """
    await update_trip_status(trip_id, 'active', activated_by)

    await log_trip_event(
        trip_id=trip_id,
        event_type="activated",
        description="Рейс активирован",
        created_by=activated_by
    )

    logger.info(f"Trip {trip_id} activated by {activated_by}")


async def update_trip_status(
    trip_id: int,
    new_status: str,
    updated_by: Optional[int] = None
) -> None:
    """
    Обновить статус рейса.

    Args:
        trip_id: ID рейса
        new_status: Новый статус
        updated_by: Кто обновил (user_id)
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_schema(conn)

        # Обновляем статус
        await conn.execute("""
            UPDATE trips SET status = ? WHERE trip_id = ?
        """, (new_status, trip_id))

        # Обновляем соответствующие временные метки
        if new_status == 'loading':
            await conn.execute("""
                UPDATE trips SET loading_confirmed_at = ? WHERE trip_id = ?
            """, (datetime.now().isoformat(), trip_id))
        elif new_status == 'unloading':
            await conn.execute("""
                UPDATE trips SET unloading_confirmed_at = ? WHERE trip_id = ?
            """, (datetime.now().isoformat(), trip_id))
        elif new_status == 'completed':
            await conn.execute("""
                UPDATE trips SET completed_at = ? WHERE trip_id = ?
            """, (datetime.now().isoformat(), trip_id))

        await conn.commit()

    # Логируем событие
    await log_trip_event(
        trip_id=trip_id,
        event_type="status_changed",
        description=f"Статус изменен на: {new_status}",
        created_by=updated_by
    )

    logger.info(f"Trip {trip_id} status updated to {new_status}")


async def log_trip_event(
    trip_id: int,
    event_type: str,
    description: Optional[str] = None,
    created_by: Optional[int] = None,
    metadata: Optional[str] = None
) -> None:
    """
    Логировать событие рейса.

    Args:
        trip_id: ID рейса
        event_type: Тип события
        description: Описание события
        created_by: Кто создал событие (user_id)
        metadata: Дополнительные данные (JSON)
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_schema(conn)

        await conn.execute("""
            INSERT INTO trip_events (
                trip_id, event_type, description, created_at, created_by, metadata
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            trip_id, event_type, description,
            datetime.now().isoformat(), created_by, metadata
        ))

        await conn.commit()

    logger.debug(f"Logged event '{event_type}' for trip {trip_id}")


async def get_trip_events(trip_id: int, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Получить события рейса.

    Args:
        trip_id: ID рейса
        limit: Максимальное количество событий

    Returns:
        List[Dict]: Список событий
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_schema(conn)
        conn.row_factory = aiosqlite.Row

        async with conn.execute("""
            SELECT * FROM trip_events
            WHERE trip_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (trip_id, limit)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_all_trips(
    status: Optional[str] = None,
    curator_id: Optional[int] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Получить все рейсы с фильтрацией.

    Args:
        status: Фильтр по статусу
        curator_id: Фильтр по куратору
        limit: Максимальное количество

    Returns:
        List[Dict]: Список рейсов
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_schema(conn)
        conn.row_factory = aiosqlite.Row

        query = "SELECT * FROM trips WHERE 1=1"
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


# ============================================================================
# Функции для редактирования рейсов
# ============================================================================

async def update_trip_phone(trip_id: int, phone: str) -> None:
    """Обновить номер телефона рейса."""
    # Нормализуем телефон
    phone = normalize_phone(phone)

    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "UPDATE trips SET phone = ? WHERE trip_id = ?",
            (phone, trip_id)
        )
        await conn.commit()
        logger.info(f"Updated phone for trip {trip_id} to {phone}")


async def update_trip_addresses(
    trip_id: int,
    loading_address: str,
    unloading_address: str
) -> None:
    """Обновить адреса рейса."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "UPDATE trips SET loading_address = ?, unloading_address = ? WHERE trip_id = ?",
            (loading_address, unloading_address, trip_id)
        )
        await conn.commit()
        logger.info(f"Updated addresses for trip {trip_id}")


async def update_trip_dates(
    trip_id: int,
    loading_date: str,
    unloading_date: str
) -> None:
    """Обновить даты рейса."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "UPDATE trips SET loading_date = ?, unloading_date = ? WHERE trip_id = ?",
            (loading_date, unloading_date, trip_id)
        )
        await conn.commit()
        logger.info(f"Updated dates for trip {trip_id}")


async def update_trip_rate(trip_id: int, rate: float) -> None:
    """Обновить ставку рейса."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "UPDATE trips SET rate = ? WHERE trip_id = ?",
            (rate, trip_id)
        )
        await conn.commit()
        logger.info(f"Updated rate for trip {trip_id} to {rate}")

