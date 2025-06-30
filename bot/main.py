import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta

import aiosqlite

import db

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import CommandStart
from dotenv import load_dotenv

from .handlers.start import start
from .handlers.location import router as location_router

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")


async def remind_once_a_day(bot: Bot) -> None:
    """Send a daily reminder if a user didn't share a point in the last 24 h."""
    query = (
        "SELECT user_id, MAX(strftime('%s', ts)) as last_ts "
        "FROM points "
        "GROUP BY user_id "
        "HAVING last_ts < strftime('%s', 'now') - 24*3600"
    )
    while True:
        try:
            async with aiosqlite.connect(db.DB_PATH) as conn:
                await db._ensure_schema(conn)
                async with conn.execute(query) as cur:
                    rows = await cur.fetchall()
                    user_ids = [row[0] for row in rows]
        except Exception:
            logger.exception("Failed to fetch users for daily reminder")
            await asyncio.sleep(30 * 60)
            continue

        for uid in user_ids:
            try:
                await bot.send_message(
                    uid,
                    "Напоминание! Пожалуйста, нажмите “Поделиться местоположением”.",
                )
            except Exception:
                logger.exception("Failed to send daily reminder to %s", uid)

        await asyncio.sleep(30 * 60)


async def alert_if_stale_live(bot: Bot) -> None:
    """Remind users to extend Telegram Live Location when it expired."""
    while True:
        try:
            async with aiosqlite.connect(db.DB_PATH) as conn:
                await db._ensure_schema(conn)
                async with conn.execute("SELECT DISTINCT user_id FROM points") as cur:
                    rows = await cur.fetchall()
                    user_ids = [row[0] for row in rows]
        except Exception:
            logger.exception("Failed to fetch user list")
            await asyncio.sleep(30 * 60)
            continue

        now = datetime.now(timezone.utc)
        for uid in user_ids:
            try:
                point = await db.get_last_point(uid)
            except Exception:
                logger.exception("Failed to get last point for %s", uid)
                continue
            if not point:
                continue
            if now - point["ts"] > timedelta(hours=7):
                try:
                    await bot.send_message(uid, "Пожалуйста, продлите Live Location")
                except Exception:
                    logger.exception("Failed to send reminder to %s", uid)

        await asyncio.sleep(30 * 60)

async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")

    bot = Bot(BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.register(start, CommandStart())
    dp.include_router(location_router)

    asyncio.create_task(remind_once_a_day(bot))
    asyncio.create_task(alert_if_stale_live(bot))

    logger.info("Starting polling")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
