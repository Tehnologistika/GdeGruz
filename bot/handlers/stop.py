

"""
Handler for the “Закончить отслеживание” button.

• Уведомляет водителя, что отслеживание прекращено.
• Шлёт сообщение в диспетчерскую группу о завершении.
"""

from aiogram import Router, F, types

from bot.keyboards import help_kb  # показываем клавиатуру «Помощь»
from db import get_phone, set_active

import os
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0"))

router = Router(name=__name__)


@router.message(F.text == "Закончить отслеживание")
async def stop_tracking(message: types.Message):
    """
    Driver pressed “Закончить отслеживание”.
    1) подтверждаем водителю;
    2) шлём уведомление в группу (если настроена);
    3) отправляем клавиатуру «Помощь» (только кнопка /help).
    """
    # 1. Ответ водителю
    await message.answer(
        "Отслеживание остановлено ✅\n"
        "Спасибо! Если нужно возобновить — снова нажмите «Поделиться местоположением».",
        reply_markup=help_kb(),
    )
    
    # помечаем водителя как неактивного
    await set_active(message.from_user.id, False)

    # 2. Уведомление диспетчерской
    if GROUP_CHAT_ID:
        phone = await get_phone(message.from_user.id)
        caption = (
            f"🚫 Водитель 📞 {phone} прекратил отслеживание."
            if phone
            else f"🚫 Водитель {message.from_user.id} прекратил отслеживание."
        )
        try:
            await message.bot.send_message(GROUP_CHAT_ID, caption)
        except Exception as exc:
            # не критично, просто записываем в лог
            import logging
            logging.getLogger(__name__).warning("Не удалось уведомить группу: %s", exc)