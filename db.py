import logging
from datetime import datetime
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

DB_PATH = Path("data/points.db")


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
