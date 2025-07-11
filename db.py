import logging
from datetime import datetime
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

DB_PATH = Path("data/points.db")


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
    """Create drivers table and `active` column if they do not exist."""
    # base table
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS drivers (
            user_id INTEGER PRIMARY KEY,
            phone   TEXT,
            active  INTEGER NOT NULL DEFAULT 1   -- 1 = tracking on
        )
        """
    )
    # add column to old installations (SQLite allows IF NOT EXISTS only from 3.35)
    try:
        await db.execute("ALTER TABLE drivers ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
    except aiosqlite.OperationalError:
        # column already exists
        pass
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


async def save_phone(user_id: int, phone: str) -> None:
    """Persist a phone number in SQLite."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_driver_schema(db)
        await db.execute(
            """
            INSERT INTO drivers(user_id, phone, active) VALUES(?, ?, 1)
            ON CONFLICT(user_id) DO UPDATE SET phone=excluded.phone, active=1
            """,
            (user_id, phone),
        )
        await db.commit()
    logger.info("Saved phone for %s", user_id)


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
    """Enable/disable tracking for a driver."""
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_driver_schema(db)
        await db.execute(
            """
            INSERT INTO drivers(user_id, active) VALUES(?, ?)
            ON CONFLICT(user_id) DO UPDATE SET active=excluded.active
            """,
            (user_id, int(flag)),
        )
        await db.commit()
    logger.info("Set active=%s for %s", flag, user_id)


async def is_active(user_id: int) -> bool:
    """Return True if driver is active (default=True)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_driver_schema(db)
        async with db.execute(
            "SELECT active FROM drivers WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
    return bool(row[0]) if row else True
