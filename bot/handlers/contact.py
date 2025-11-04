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
    """
    Сохранение контакта и проверка назначенных рейсов.

    При первой регистрации проверяем, есть ли рейсы
    назначенные на этот телефон.
    """
    phone = msg.contact.phone_number
    user_id = msg.from_user.id

    # Сохраняем телефон
    await save_phone(user_id, phone)

    # Проверяем, есть ли назначенные рейсы
    import db_trips
    assigned_trips = await db_trips.get_trips_by_phone(phone, status='assigned')

    if not assigned_trips:
        # Нет назначенных рейсов
        await msg.answer(
            f"✅ Спасибо! Номер {phone} сохранён.\n\n"
            f"Новых рейсов пока нет.\n"
            f"Ожидайте назначения от куратора.",
            reply_markup=location_kb()
        )

        # Уведомляем кураторов о новом водителе
        if GROUP_CHAT_ID:
            try:
                from datetime import datetime
                await msg.bot.send_message(
                    GROUP_CHAT_ID,
                    f"🆕 **Новый водитель зарегистрировался**\n\n"
                    f"📞 {phone}\n"
                    f"🆔 User ID: {user_id}\n"
                    f"👤 {msg.from_user.full_name}\n"
                    f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.warning(f"Failed to notify curators: {e}")

        return

    # Есть назначенные рейсы!
    trip = assigned_trips[0]  # Берем первый

    # Обновляем user_id в рейсе
    await db_trips.update_trip_user_id(trip['trip_id'], user_id)

    # Формируем inline-кнопки
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Активировать рейс", callback_data=f"activate_my_trip:{trip['trip_id']}")
    kb.button(text="ℹ️ Подробнее", callback_data=f"view_my_trip:{trip['trip_id']}")
    kb.adjust(1, 1)

    await msg.answer(
        f"✅ Спасибо! Номер {phone} сохранён.\n\n"
        f"🔍 Проверяю назначенные рейсы...\n\n"
        f"✨ Найден рейс **#{trip['trip_number']}**!\n\n"
        f"🚚 Рейс #{trip['trip_number']}\n"
        f"📍 {trip['loading_address']}\n"
        f"     ↓\n"
        f"📍 {trip['unloading_address']}\n"
        f"📅 Погрузка: {trip['loading_date']}\n"
        f"📅 Выгрузка: {trip['unloading_date']}\n"
        f"💰 Ставка: {trip['rate']:,.0f} ₽\n\n"
        f"Этот рейс назначен вам.",
        reply_markup=kb.as_markup(),
        parse_mode="Markdown"
    )


# /help handler
@router.message(Command("help"))
@router.message(F.text.in_(["❓ Помощь", "Помощь", "помощь"]))
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
