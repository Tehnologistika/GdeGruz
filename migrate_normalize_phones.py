#!/usr/bin/env python3
"""
Миграция: нормализация всех номеров телефонов в базе данных.

Применяет функцию normalize_phone() ко всем существующим записям в таблицах:
- drivers (phone)
- trips (phone)
"""

import asyncio
import logging
from pathlib import Path
import aiosqlite

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Импортируем функцию нормализации
from db import normalize_phone

DRIVERS_DB_PATH = Path("/home/git/fleet-live-bot/userdata/points.db")
TRIPS_DB_PATH = Path("/home/git/fleet-live-bot/userdata/trips.db")


async def migrate_drivers_table():
    """Нормализовать номера телефонов в таблице drivers."""
    logger.info("Starting migration for drivers table...")

    if not DRIVERS_DB_PATH.exists():
        logger.warning(f"Database not found: {DRIVERS_DB_PATH}")
        return

    async with aiosqlite.connect(DRIVERS_DB_PATH) as db:
        # Получаем все записи с телефонами
        async with db.execute("SELECT user_id, phone FROM drivers WHERE phone IS NOT NULL") as cursor:
            rows = await cursor.fetchall()

        logger.info(f"Found {len(rows)} driver records with phone numbers")

        updated_count = 0
        for user_id, phone in rows:
            if not phone:
                continue

            # Нормализуем номер
            normalized_phone = normalize_phone(phone)

            # Обновляем только если изменился
            if normalized_phone != phone:
                await db.execute(
                    "UPDATE drivers SET phone = ? WHERE user_id = ?",
                    (normalized_phone, user_id)
                )
                logger.info(f"Updated driver {user_id}: {phone} -> {normalized_phone}")
                updated_count += 1

        await db.commit()
        logger.info(f"Drivers table migration complete. Updated {updated_count} records.")


async def migrate_trips_table():
    """Нормализовать номера телефонов в таблице trips."""
    logger.info("Starting migration for trips table...")

    if not TRIPS_DB_PATH.exists():
        logger.warning(f"Database not found: {TRIPS_DB_PATH}")
        return

    async with aiosqlite.connect(TRIPS_DB_PATH) as db:
        # Получаем все записи с телефонами
        async with db.execute("SELECT trip_id, phone FROM trips WHERE phone IS NOT NULL") as cursor:
            rows = await cursor.fetchall()

        logger.info(f"Found {len(rows)} trip records with phone numbers")

        updated_count = 0
        for trip_id, phone in rows:
            if not phone:
                continue

            # Нормализуем номер
            normalized_phone = normalize_phone(phone)

            # Обновляем только если изменился
            if normalized_phone != phone:
                await db.execute(
                    "UPDATE trips SET phone = ? WHERE trip_id = ?",
                    (normalized_phone, trip_id)
                )
                logger.info(f"Updated trip {trip_id}: {phone} -> {normalized_phone}")
                updated_count += 1

        await db.commit()
        logger.info(f"Trips table migration complete. Updated {updated_count} records.")


async def main():
    """Запустить все миграции."""
    logger.info("="*60)
    logger.info("Starting phone normalization migration")
    logger.info("="*60)

    try:
        await migrate_drivers_table()
        await migrate_trips_table()

        logger.info("="*60)
        logger.info("Migration completed successfully!")
        logger.info("="*60)
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
