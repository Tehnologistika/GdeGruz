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
from db import get_phone

GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0"))
ESCALATE_DELAY = timedelta(hours=REMIND_HOURS + 2)

# === intervals (in hours) ===
REMIND_HOURS = float(os.getenv("REMIND_HOURS", "0.2"))  # 0.2 h ≈ 12 min for testing
POLL_MINUTES = 30  # db polling step, default 30 min; will be overridden below for tests

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))


async def remind_every_12h(bot: Bot) -> None:
    while True:
        now = datetime.now(timezone.utc)
        # fetch current list of drivers on each cycle
        try:
            async with aiosqlite.connect(db.DB_PATH) as conn:
                await db._ensure_schema(conn)
                async with conn.execute("SELECT DISTINCT user_id FROM points") as cur:
                    rows = await cur.fetchall()
                    user_ids = [row[0] for row in rows]
        except Exception as err:
            logger.exception("Failed to fetch user list: %s", err)
            await asyncio.sleep(POLL_MINUTES * 60)
            continue

        for uid in user_ids:
            try:
                point = await db.get_last_point(uid)
            except Exception:
                ...
                continue
            if not point:
                continue

            last_ts = point["ts"]

            # 1. Личное напоминание (>12 ч)
            if now - last_ts > timedelta(hours=REMIND_HOURS):
                logger.info("Sending 12‑hour reminder to %s", uid)
                try:
                    await bot.send_message(
                        uid,
                        "Напоминание! Пожалуйста, нажмите «Поделиться местоположением»."
                    )
                except Exception:
                    logger.exception("Failed to send reminder to %s", uid)

            # 2. Эскалация в группу (>14 ч)
            if now - last_ts > ESCALATE_DELAY and GROUP_CHAT_ID:
                logger.info("Escalating: no coords from %s since %s", uid, last_ts)
                phone = await get_phone(uid)
                caption = (
                    f"⚠️ Нет координат от водителя 📞 {phone} с {last_ts:%d.%m %H:%M}"
                    if phone else
                    f"⚠️ Нет координат от водителя {uid} с {last_ts:%d.%m %H:%M}"
                )
                try:
                    await bot.send_message(GROUP_CHAT_ID, caption)
                except Exception as e:
                    logger.warning("Не удалось отправить эскалацию: %s", e)

        # shorter sleep for testing; use REMIND_HOURS to derive minutes
        await asyncio.sleep(max(int(REMIND_HOURS * 60), 2) * 60)

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
