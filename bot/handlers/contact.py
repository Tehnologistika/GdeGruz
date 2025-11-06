"""
Обработчики регистрации водителей.

Процесс регистрации:
1. Водитель делится номером телефона
2. Бот проверяет, зарегистрирован ли он в системе
3. Если да → приветствие по имени + проверка рейсов
4. Если нет → запрос имени → сохранение → проверка рейсов
"""

import logging
import os
from datetime import datetime

from aiogram import F, Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db import (
    save_phone,
    get_phone,
    get_driver_by_phone,
    get_driver_by_user_id,
    save_driver_name,
)
from ..keyboards import location_kb

logger = logging.getLogger(__name__)

router = Router()

GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0"))


class RegistrationStates(StatesGroup):
    """Состояния процесса регистрации водителя."""
    waiting_for_name = State()


@router.message(F.contact)
async def save_contact(msg: Message, state: FSMContext) -> None:
    """
    Обработка получения номера телефона от водителя.

    Логика:
    1. Проверяем, есть ли водитель с таким phone в БД
    2. Если есть и имя заполнено → приветствие по имени
    3. Если есть но имени нет → запрашиваем имя
    4. Если нет → создаем запись и запрашиваем имя
    """
    from db import normalize_phone

    phone = msg.contact.phone_number
    user_id = msg.from_user.id

    # Нормализуем телефон для использования в системе
    normalized_phone = normalize_phone(phone)

    # Проверяем, существует ли водитель с таким телефоном
    existing_driver = await get_driver_by_phone(normalized_phone)

    if existing_driver and existing_driver.get('name'):
        # Водитель уже зарегистрирован - приветствуем по имени
        driver_name = existing_driver['name']

        # Обновляем телефон (может быть новый user_id)
        await save_phone(user_id, normalized_phone, driver_name)

        # Проверяем назначенные рейсы
        import db_trips
        assigned_trips = await db_trips.get_trips_by_phone(normalized_phone, status='assigned')

        if not assigned_trips:
            # Нет новых рейсов
            await msg.answer(
                f"👋 Рады видеть вас снова, {driver_name}!\n\n"
                f"📞 Номер {normalized_phone} подтвержден.\n"
                f"Новых рейсов пока нет.\n\n"
                f"Ожидайте назначения от куратора.",
                reply_markup=location_kb()
            )

            # Уведомляем кураторов
            if GROUP_CHAT_ID:
                try:
                    await msg.bot.send_message(
                        GROUP_CHAT_ID,
                        f"🔄 **Водитель вернулся в систему**\n\n"
                        f"👤 {driver_name}\n"
                        f"📞 {normalized_phone}\n"
                        f"🆔 User ID: {user_id}\n"
                        f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.warning(f"Failed to notify curators: {e}")
        else:
            # Есть назначенные рейсы!
            trip = assigned_trips[0]

            # Обновляем user_id в рейсе
            await db_trips.update_trip_user_id(trip['trip_id'], user_id)

            # Формируем inline-кнопки
            kb = InlineKeyboardBuilder()
            kb.button(text="✅ Активировать рейс", callback_data=f"activate_my_trip:{trip['trip_id']}")
            kb.button(text="ℹ️ Подробнее", callback_data=f"view_my_trip:{trip['trip_id']}")
            kb.adjust(1, 1)

            await msg.answer(
                f"👋 Рады видеть вас снова, {driver_name}!\n\n"
                f"📞 Номер {normalized_phone} подтвержден.\n"
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

    else:
        # Новый водитель или нет имени - запрашиваем имя
        # Сохраняем телефон в БД
        await save_phone(user_id, normalized_phone)

        # Сохраняем данные в состояние
        await state.update_data(phone=normalized_phone, user_id=user_id)
        await state.set_state(RegistrationStates.waiting_for_name)

        # Запрашиваем имя
        await msg.answer(
            f"✅ Спасибо! Номер {normalized_phone} сохранён.\n\n"
            f"📝 **Пожалуйста, напишите ваше имя**\n"
            f"(как к вам обращаться)",
            reply_markup=location_kb()
        )


@router.message(RegistrationStates.waiting_for_name)
async def process_driver_name(msg: Message, state: FSMContext) -> None:
    """
    Обработка получения имени водителя.
    """
    driver_name = msg.text.strip()

    # Валидация имени
    if not driver_name or len(driver_name) < 2:
        await msg.answer(
            "❌ Имя слишком короткое.\n"
            "Пожалуйста, напишите ваше имя (минимум 2 символа):"
        )
        return

    if len(driver_name) > 50:
        await msg.answer(
            "❌ Имя слишком длинное.\n"
            "Пожалуйста, напишите ваше имя (максимум 50 символов):"
        )
        return

    # Получаем данные из состояния
    data = await state.get_data()
    phone = data.get('phone')
    user_id = msg.from_user.id

    # Сохраняем имя
    await save_driver_name(user_id, driver_name)

    # Очищаем состояние
    await state.clear()

    # Проверяем назначенные рейсы
    import db_trips
    assigned_trips = await db_trips.get_trips_by_phone(phone, status='assigned')

    if not assigned_trips:
        # Нет назначенных рейсов
        await msg.answer(
            f"🎉 Отлично, {driver_name}!\n\n"
            f"✅ Вы успешно зарегистрированы в системе.\n"
            f"Новых рейсов пока нет.\n\n"
            f"Ожидайте назначения от куратора.",
            reply_markup=location_kb()
        )

        # Уведомляем кураторов о новом водителе
        if GROUP_CHAT_ID:
            try:
                await msg.bot.send_message(
                    GROUP_CHAT_ID,
                    f"🆕 **Новый водитель зарегистрировался**\n\n"
                    f"👤 {driver_name}\n"
                    f"📞 {phone}\n"
                    f"🆔 User ID: {user_id}\n"
                    f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.warning(f"Failed to notify curators: {e}")

    else:
        # Есть назначенные рейсы!
        trip = assigned_trips[0]

        # Обновляем user_id в рейсе
        await db_trips.update_trip_user_id(trip['trip_id'], user_id)

        # Формируем inline-кнопки
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Активировать рейс", callback_data=f"activate_my_trip:{trip['trip_id']}")
        kb.button(text="ℹ️ Подробнее", callback_data=f"view_my_trip:{trip['trip_id']}")
        kb.adjust(1, 1)

        await msg.answer(
            f"🎉 Отлично, {driver_name}!\n\n"
            f"✅ Вы успешно зарегистрированы в системе.\n"
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

        # Уведомляем кураторов
        if GROUP_CHAT_ID:
            try:
                await msg.bot.send_message(
                    GROUP_CHAT_ID,
                    f"🆕 **Новый водитель + рейс активирован**\n\n"
                    f"👤 {driver_name}\n"
                    f"📞 {phone}\n"
                    f"🚚 Рейс #{trip['trip_number']}\n"
                    f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.warning(f"Failed to notify curators: {e}")


# /help handler
@router.message(Command("help"))
@router.message(F.text.in_(["помощь", "Помощь", "❓ Помощь"]))
async def ask_help(msg: Message) -> None:
    """Водитель просит связаться. Дублируем запрос в диспетчерскую группу."""
    user_id = msg.from_user.id

    # Получаем информацию о водителе
    driver = await get_driver_by_user_id(user_id)

    if driver and driver.get('name'):
        driver_info = f"👤 {driver['name']} (📞 {driver['phone']})"
    elif driver and driver.get('phone'):
        driver_info = f"📞 {driver['phone']}"
    else:
        driver_info = f"🆔 {user_id}"

    if GROUP_CHAT_ID:
        try:
            await msg.bot.send_message(
                GROUP_CHAT_ID,
                f"⚠️ **Водитель просит связаться!**\n\n"
                f"{driver_info}\n"
                f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning("Не удалось отправить /help в группу: %s", e)

    await msg.answer(
        "📞 Запрос помощи отправлен диспетчеру.\n"
        "Оставайтесь на связи, с вами скоро свяжутся."
    )
