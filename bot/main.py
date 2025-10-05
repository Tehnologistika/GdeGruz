import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from dateutil.parser import isoparse

import aiosqlite
import db

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import CommandStart, Command
from dotenv import load_dotenv

from .handlers.start import start
from .handlers.location import router as location_router
from .handlers.contact import router as contact_router
from .handlers.stop import router as stop_router
from .handlers.resume import router as resume_router
from .handlers.redeploy import redeploy
from db import get_phone, is_active

# === intervals (in hours) ===
REMIND_HOURS = float(os.getenv("REMIND_HOURS", "0.2"))  # default 0.2 h ≈ 12 min

GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0"))
ESCALATE_DELAY = timedelta(hours=REMIND_HOURS + 2)      # reminder + 2 h

# minutes to wait if DB fetch fails (at least 2 min, or REMIND_HOURS*60)
POLL_MINUTES = max(int(REMIND_HOURS * 60), 2)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# ============================================================================
# FIX 1: Трекинг отправленных эскалаций (чтобы не спамить)
# ============================================================================
escalation_sent = {}  # {user_id: timestamp когда отправили эскалацию}


async def remind_every_12h(bot: Bot) -> None:
    logger.info("reminder-loop: started (REMIND_HOURS=%s)", REMIND_HOURS)
    while True:
        now = datetime.now(timezone.utc)
        
        try:
            async with aiosqlite.connect(db.DB_PATH) as conn:
                await db._ensure_schema(conn)
                
                # FIX 2: Берем только АКТИВНЫХ водителей
                # (у которых есть запись в drivers с active=1)
                query = """
                    SELECT DISTINCT p.user_id
                    FROM points p
                    INNER JOIN drivers d ON p.user_id = d.user_id
                    WHERE d.active = 1
                """
                async with conn.execute(query) as cur:
                    rows = await cur.fetchall()
                    user_ids = [row[0] for row in rows]
                    logger.debug("reminder-loop: active users=%s (now=%s)", user_ids, now)
        except Exception as err:
            logger.exception("Failed to fetch user list: %s", err)
            await asyncio.sleep(POLL_MINUTES * 60)
            continue

        for uid in user_ids:
            try:
                point = await db.get_last_point(uid)
            except Exception:
                continue
            
            if not point:
                continue

            # FIX 3: Унифицированная обработка timezone
            val = point["ts"]
            if isinstance(val, str):
                last_ts = isoparse(val).astimezone(timezone.utc)
            elif val.tzinfo is None:
                # naive datetime - считаем UTC
                last_ts = val.replace(tzinfo=timezone.utc)
            else:
                last_ts = val.astimezone(timezone.utc)

            time_since_last = now - last_ts

            # 1. Личное напоминание (>REMIND_HOURS h)
            if time_since_last > timedelta(hours=REMIND_HOURS):
                logger.info("Sending %.2f‑hour reminder to %s", REMIND_HOURS, uid)
                try:
                    await bot.send_message(
                        uid,
                        "Напоминание! Пожалуйста, нажмите «Поделиться местоположением»."
                    )
                except Exception as exc:
                    logger.exception("Failed to send reminder to %s: %s", uid, exc)

            # 2. Эскалация в группу (>REMIND_HOURS + 2 h)
            # FIX 4: Отправляем эскалацию только ОДИН РАЗ
            if time_since_last > ESCALATE_DELAY and GROUP_CHAT_ID:
                # Проверяем, не отправляли ли уже эскалацию
                last_escalation = escalation_sent.get(uid)
                
                # Отправляем эскалацию, если:
                # - ещё не отправляли OR
                # - с последней эскалации прошло >12 часов (чтобы напомнить снова)
                should_escalate = (
                    last_escalation is None or 
                    (now - last_escalation) > timedelta(hours=12)
                )
                
                if should_escalate:
                    logger.info("Escalating: no coords from %s since %s", uid, last_ts)
                    phone = await get_phone(uid)
                    caption = (
                        f"⚠️ Нет координат от водителя 📞 {phone} с {last_ts:%d.%m %H:%M} UTC"
                        if phone else
                        f"⚠️ Нет координат от водителя {uid} с {last_ts:%d.%m %H:%M} UTC"
                    )
                    try:
                        await bot.send_message(GROUP_CHAT_ID, caption)
                        escalation_sent[uid] = now  # Запоминаем время эскалации
                    except Exception as e:
                        logger.warning("Не удалось отправить эскалацию: %s", e)
            
            # FIX 5: Очищаем трекинг эскалации, если водитель снова активен
            if time_since_last <= timedelta(hours=REMIND_HOURS):
                escalation_sent.pop(uid, None)

        await asyncio.sleep(max(int(REMIND_HOURS * 60), 2) * 60)


async def main() -> None:
    # FIX 6: Проверка обязательных переменных
    if not BOT_TOKEN:
        raise RuntimeError("❌ BOT_TOKEN не установлен в .env")
    
    if not GROUP_CHAT_ID:
        logger.warning("⚠️  GROUP_CHAT_ID не установлен - уведомления в группу отключены")
    
    if not ADMIN_ID:
        logger.warning("⚠️  ADMIN_ID не установлен - команда /redeploy недоступна")

    await db.init()

    bot = Bot(BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.register(start, CommandStart())
    dp.message.register(redeploy, Command("redeploy"))
    dp.include_router(location_router)
    dp.include_router(contact_router)
    dp.include_router(stop_router)
    dp.include_router(resume_router)

    # Запускаем фоновую задачу
    reminder_task = asyncio.create_task(remind_every_12h(bot))

    try:
        logger.info("🚀 Starting polling")
        await dp.start_polling(bot)
    finally:
        # FIX 7: Graceful shutdown
        reminder_task.cancel()
        try:
            await reminder_task
        except asyncio.CancelledError:
            pass
        await bot.session.close()
        logger.info("🛑 Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
