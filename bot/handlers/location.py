import logging
from datetime import datetime, timezone
import os
from aiogram import Bot
from aiogram.types import Message

from ..storage import save_point


logger = logging.getLogger(__name__)

# ID группы диспетчеров, куда дублируем все координаты
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0"))


async def location(message: Message) -> None:
    """Handle incoming location messages."""
    if not message.location:
        return

    user_id = message.from_user.id if message.from_user else 0
    lat = message.location.latitude
    lon = message.location.longitude
    ts = datetime.now(timezone.utc)

    logger.info("Received location from %s: %s, %s", user_id, lat, lon)
    await save_point(user_id=user_id, lat=lat, lon=lon, ts=ts)

    # Дублируем точку в группу диспетчеров, если ID задан
    if GROUP_CHAT_ID:
        bot: Bot = message.bot
        try:
            await bot.send_location(
                chat_id=GROUP_CHAT_ID,
                latitude=lat,
                longitude=lon,
                disable_notification=True,
            )
            await bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=f"Водитель {user_id} • {ts.astimezone().strftime('%Y-%m-%d %H:%M')}",
                disable_notification=True,
            )
        except Exception as e:
            logger.warning("Не удалось отправить точку в группу: %s", e)

    await message.answer("Спасибо, местоположение сохранено!")
