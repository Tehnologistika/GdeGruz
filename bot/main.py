import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta

import aiosqlite

import db

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import CommandStart, Command
from dotenv import load_dotenv

from .handlers.start import start
from .handlers.location import router as location_router
from .handlers.contact import router as contact_router
from .handlers.redeploy import redeploy

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))


async def remind_every_12h(bot: Bot) -> None:
    """Periodically (every 30 min) напоминает водителю нажать
    «Поделиться местоположением», если точка не обновлялась 12 ч."""
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
            if now - point["ts"] > timedelta(hours=12):
                try:
                    await bot.send_message(
                        uid,
                        "Напоминание! Пожалуйста, нажмите «Поделиться местоположением»."
                    )
                except Exception:
                    logger.exception("Failed to send reminder to %s", uid)

        await asyncio.sleep(30 * 60)

async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")

    await db.init()

    bot = Bot(BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.register(start, CommandStart())
    dp.message.register(redeploy, Command("redeploy"))
    dp.include_router(location_router)
    dp.include_router(contact_router)

    asyncio.create_task(remind_every_12h(bot))

    logger.info("Starting polling")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
