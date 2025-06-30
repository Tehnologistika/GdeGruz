import logging

from aiogram import F, Router
from aiogram.types import Message

from db import save_phone

logger = logging.getLogger(__name__)

router = Router()


@router.message(F.contact)
async def save_contact(msg: Message) -> None:
    phone = msg.contact.phone_number
    user = msg.from_user.id

    await save_phone(user, phone)

    await msg.answer(
        "Спасибо! Номер сохранён — можно делиться местоположением."
    )

