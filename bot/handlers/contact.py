import logging

from aiogram import F, Router
from aiogram.types import Message

from db import save_phone

import os
from aiogram.filters import Command
from db import get_phone

GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0"))
from ..keyboards import location_kb

logger = logging.getLogger(__name__)

router = Router()


@router.message(F.contact)
async def save_contact(msg: Message) -> None:
    phone = msg.contact.phone_number
    user = msg.from_user.id

    await save_phone(user, phone)

    await msg.answer(
        "Спасибо! Номер сохранён — теперь делитесь местоположением каждые 12 часов.",
        reply_markup=location_kb(),
    )


# /help handler
@router.message(Command("help"))
@router.message(lambda m: m.text and m.text.lower() == "помощь")
async def ask_help(msg: Message) -> None:
    """Водитель просит связаться. Дублируем запрос в диспетчерскую группу."""
    user = msg.from_user.id
    phone = await get_phone(user)
    if GROUP_CHAT_ID:
        caption = (
            f"⚠️ Водитель 📞 {phone} просит связаться!"
            if phone else
            f"⚠️ Водитель {user} просит связаться!"
        )
        try:
            await msg.bot.send_message(GROUP_CHAT_ID, caption)
        except Exception as e:
            logger.warning("Не удалось отправить /help в группу: %s", e)

    await msg.answer("Запрос помощи отправлен диспетчеру. Оставайтесь на связи.")
