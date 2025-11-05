import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite

logger = logging.getLogger(__name__)

DB_PATH = Path("/home/git/fleet-live-bot/userdata/points.db")


async def init() -> None:
    """Initialize database and create missing tables."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_schema(db)
        await _ensure_driver_schema(db)


async def _ensure_schema(db: aiosqlite.Connection) -> None:
    """Create table and index if they do not exist."""
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            ts TEXT NOT NULL
        )
        """
    )
    await db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_points_user_ts
            ON points(user_id, ts DESC)
        """
    )
    await db.commit()


async def _ensure_driver_schema(db: aiosqlite.Connection) -> None:
    """Create drivers table and add missing columns if they do not exist."""
    # base table
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS drivers (
            user_id INTEGER PRIMARY KEY,
            phone TEXT,
            name TEXT,
            registered_at TEXT,
            active INTEGER NOT NULL DEFAULT 1
        )
        """
    )

    # Add columns for old installations (SQLite doesn't support IF NOT EXISTS for ALTER TABLE)
    columns_to_add = [
        ("active", "INTEGER NOT NULL DEFAULT 1"),
        ("name", "TEXT"),
        ("registered_at", "TEXT"),
    ]

    for col_name, col_type in columns_to_add:
        try:
            await db.execute(f"ALTER TABLE drivers ADD COLUMN {col_name} {col_type}")
        except aiosqlite.OperationalError:
            # column already exists
            pass

    # Create index on phone for faster lookups
    await db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_drivers_phone ON drivers(phone)
        """
    )

    await db.commit()


async def save_point(user_id: int, lat: float, lon: float, ts: datetime) -> None:
    """Persist a location in SQLite."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_schema(db)
        await db.execute(
            "INSERT INTO points(user_id, lat, lon, ts) VALUES(?, ?, ?, ?)",
            (user_id, lat, lon, ts.isoformat()),
        )
        await db.commit()
    logger.info("Saved point for %s", user_id)


async def get_last_point(user_id: int):
    """Retrieve the most recent point for a user."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_schema(db)
        async with db.execute(
            """
            SELECT id, user_id, lat, lon, ts
              FROM points
             WHERE user_id = ?
             ORDER BY ts DESC
             LIMIT 1
            """,
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        id_, uid, lat, lon, ts_str = row
        return {
            "id": id_,
            "user_id": uid,
            "lat": lat,
            "lon": lon,
            "ts": datetime.fromisoformat(ts_str),
        }


async def save_phone(user_id: int, phone: str, name: str = None) -> None:
    """
    Persist a phone number and name in SQLite.

    Args:
        user_id: Telegram user ID
        phone: Phone number
        name: Driver name (optional, can be set later)
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_driver_schema(db)

        # Check if driver already exists
        async with db.execute(
            "SELECT user_id, name, registered_at FROM drivers WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            existing = await cursor.fetchone()

        if existing:
            # Update existing driver (preserve name and registered_at if they exist)
            await db.execute(
                """
                UPDATE drivers
                SET phone = ?,
                    name = COALESCE(?, name),
                    active = 1
                WHERE user_id = ?
                """,
                (phone, name, user_id),
            )
        else:
            # New driver - set registered_at
            await db.execute(
                """
                INSERT INTO drivers(user_id, phone, name, registered_at, active)
                VALUES(?, ?, ?, ?, 1)
                """,
                (user_id, phone, name, datetime.now().isoformat()),
            )

        await db.commit()
    logger.info("Saved phone for %s (name: %s)", user_id, name or "not set")


async def get_phone(user_id: int) -> str | None:
    """Fetch a driver's phone by Telegram user id."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_driver_schema(db)
        async with db.execute(
            "SELECT phone FROM drivers WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return row[0] if row else None


async def get_user_id_by_phone(phone: str) -> Optional[int]:
    """
    Получить Telegram user_id водителя по номеру телефона.

    Args:
        phone: Номер телефона (+79991234567)

    Returns:
        int | None: Telegram user_id или None если не найден
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_driver_schema(db)
        async with db.execute("""
            SELECT user_id FROM drivers WHERE phone = ?
        """, (phone,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def get_driver_by_user_id(user_id: int) -> Optional[dict]:
    """
    Получить информацию о водителе по Telegram user_id.

    Args:
        user_id: Telegram user ID

    Returns:
        dict | None: Данные водителя или None
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_driver_schema(db)
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT user_id, phone, name, registered_at, active
            FROM drivers WHERE user_id = ?
        """, (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_driver_by_phone(phone: str) -> Optional[dict]:
    """
    Получить информацию о водителе по номеру телефона.

    Args:
        phone: Номер телефона

    Returns:
        dict | None: Данные водителя или None
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_driver_schema(db)
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT user_id, phone, name, registered_at, active
            FROM drivers WHERE phone = ?
        """, (phone,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def save_driver_name(user_id: int, name: str) -> None:
    """
    Сохранить/обновить имя водителя.

    Args:
        user_id: Telegram user ID
        name: Имя водителя
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_driver_schema(db)
        await db.execute("""
            UPDATE drivers SET name = ? WHERE user_id = ?
        """, (name, user_id))
        await db.commit()
    logger.info("Saved name '%s' for user %s", name, user_id)


async def is_driver_registered(user_id: int) -> bool:
    """
    Проверить, зарегистрирован ли водитель (есть ли имя).

    Args:
        user_id: Telegram user ID

    Returns:
        bool: True если зарегистрирован (имеет имя)
    """
    driver = await get_driver_by_user_id(user_id)
    return driver is not None and driver.get('name') is not None




async def get_last_points() -> list[tuple[int, datetime]]:
    """Return list of (user_id, ts) where ts is the latest point timestamp per driver."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_schema(db)
        query = """
            SELECT user_id, MAX(ts)
              FROM points
          GROUP BY user_id
        """
        async with db.execute(query) as cur:
            rows = await cur.fetchall()
        # rows: list[(uid, ts_str)]
        return [
            (uid, datetime.fromisoformat(ts_str))
            for uid, ts_str in rows
            if ts_str is not None
        ]

# ---------------------------------------------------------------------------
# tracking control helpers
# ---------------------------------------------------------------------------

async def set_active(user_id: int, flag: bool) -> None:
    """Enable/disable tracking for a driver.

    When flag=True (водитель снова активен) – удаляем его старые точки,
    чтобы счётчик 12‑часовых напоминаний начинался «с чистого листа».
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_driver_schema(db)

        # 1) Обновляем флаг в таблице drivers
        await db.execute(
            """
            INSERT INTO drivers(user_id, active) VALUES(?, ?)
            ON CONFLICT(user_id) DO UPDATE SET active=excluded.active
            """,
            (user_id, int(flag)),
        )

        # 2) Если отслеживание вновь включено – очищаем предыдущие точки
        if flag:
            await db.execute("DELETE FROM points WHERE user_id = ?", (user_id,))

        await db.commit()

    logger.info("Set active=%s for %s (old points %s)",
                flag, user_id, "purged" if flag else "kept")


async def is_active(user_id: int) -> bool:
    """Return True if driver is active (default=True)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_driver_schema(db)
        async with db.execute(
            "SELECT active FROM drivers WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
    return bool(row[0]) if row else True


async def clear_all() -> None:
    """Remove all stored drivers and location points."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_schema(db)
        await _ensure_driver_schema(db)
        await db.execute("DELETE FROM points")
        await db.execute("DELETE FROM drivers")
        await db.commit()
    logger.info("Database cleared")
