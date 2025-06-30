from aiogram import Router, F, Bot
from aiogram.types import Message

import os, logging
from db import save_point, get_phone

logger = logging.getLogger(__name__)

router = Router()

GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0"))

@router.message(F.location)
async def handle_location(msg: Message):
    user_id = msg.from_user.id
    lat = msg.location.latitude
    lon = msg.location.longitude
    ts = msg.date

    await save_point(user_id, lat, lon, ts)

    # дублируем в группу
    if GROUP_CHAT_ID:
        bot: Bot = msg.bot
        phone = await get_phone(user_id)
        caption = f"📞 {phone}" if phone else f"Водитель {user_id}"
        try:
            await bot.send_location(GROUP_CHAT_ID, lat, lon, disable_notification=True)
            await bot.send_message(GROUP_CHAT_ID, caption, disable_notification=True)
        except Exception as e:
            logger.warning("Не удалось отправить точку в группу: %s", e)

    await msg.answer("Спасибо, местоположение сохранено!")