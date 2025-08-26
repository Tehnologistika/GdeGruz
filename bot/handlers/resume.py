

"""
Handler for the “Возобновить отслеживание” button.

• Ставит active = 1 (включает трекинг).
• Возвращает водителю основную клавиатуру с кнопкой локации.
• Уведомляет диспетчерскую группу.
"""

from aiogram import Router, F, types
import os
import logging

from db import set_active, get_phone
from bot.keyboards import location_kb

GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0"))

router = Router(name=__name__)


@router.message(F.text == "Возобновить отслеживание")
async def resume_tracking(message: types.Message):
    uid = message.from_user.id

    # 1. Активируем трекинг
    await set_active(uid, True)

    # 2. Сообщаем водителю и отдаём клавиатуру
    await message.answer(
        "Отслеживание возобновлено ✅\n"
        "Не забудьте отправлять местоположение каждые 12 часов.",
        reply_markup=location_kb(),
    )

    # 3. Уведомляем диспетчерскую группу
    if GROUP_CHAT_ID:
        phone = await get_phone(uid)
        caption = (
            f"✅ Водитель 📞 {phone} возобновил отслеживание."
            if phone else
            f"✅ Водитель {uid} возобновил отслеживание."
        )
        try:
            await message.bot.send_message(GROUP_CHAT_ID, caption)
        except Exception as exc:
            logging.getLogger(__name__).warning("Не удалось уведомить группу: %s", exc)