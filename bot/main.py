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
from datetime import datetime, timedelta, timezone
import os

from db import get_last_points, get_phone  # добавьте, если ещё нет

GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0"))
ESCALATE_DELAY = timedelta(hours=14)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))


async def remind_every_12h(bot: Bot) -> None:
    ...
    now = datetime.now(timezone.utc)
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
        if now - last_ts > timedelta(hours=12):
            try:
                await bot.send_message(
                    uid,
                    "Напоминание! Пожалуйста, нажмите «Поделиться местоположением»."
                )
            except Exception:
                logger.exception("Failed to send reminder to %s", uid)

        # 2. Эскалация в группу (>14 ч)
        if now - last_ts > ESCALATE_DELAY and GROUP_CHAT_ID:
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
