"""
Обработчики для кураторов рейсов.

Доступны только пользователям с ID из CURATOR_IDS.
"""

import os
import logging
from typing import List
from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

import db_trips
from db import get_user_id_by_phone

router = Router()
logger = logging.getLogger(__name__)

# Telegram ID кураторов (из переменных окружения)
CURATOR_IDS = [int(x) for x in os.getenv("CURATOR_IDS", "").split(",") if x]
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0"))


def is_curator(user_id: int) -> bool:
    """Проверка, является ли пользователь куратором."""
    return user_id in CURATOR_IDS


class CreateTripStates(StatesGroup):
    """Состояния для создания рейса."""
    waiting_data = State()


class EditTripStates(StatesGroup):
    """Состояния для редактирования рейса."""
    waiting_phone = State()
    waiting_addresses = State()
    waiting_dates = State()
    waiting_rate = State()


def cancel_kb():
    """Inline-кнопка отмены."""
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отмена", callback_data="cancel")
    return kb.as_markup()


@router.message(Command("admin"))
async def admin_panel(message: Message):
    """
    Админ-панель для кураторов.

    Использование: /admin
    """
    if not is_curator(message.from_user.id):
        await message.answer("❌ Эта команда доступна только кураторам")
        return

    # Получаем статистику
    try:
        all_trips = await db_trips.get_all_trips(limit=1000)

        # Считаем по статусам
        stats = {
            'assigned': 0,
            'active': 0,
            'loading': 0,
            'in_transit': 0,
            'unloading': 0,
            'completed': 0,
            'total': len(all_trips)
        }

        for trip in all_trips:
            status = trip.get('status', 'unknown')
            if status in stats:
                stats[status] += 1

        # Формируем админ-панель
        kb = InlineKeyboardBuilder()
        kb.button(text="➕ Создать рейс", callback_data="new_trip")
        kb.button(text="📋 Активные рейсы", callback_data="list_active_trips")
        kb.button(text="📊 Все рейсы", callback_data="list_trips")
        kb.button(text="✅ Завершенные", callback_data="list_completed_trips")
        kb.button(text="📈 Статистика", callback_data="show_stats")
        kb.adjust(1, 2, 2, 1)

        await message.answer(
            "🎛 <b>Панель управления рейсами</b>\n\n"
            f"📊 Статистика:\n"
            f"• ⏳ Назначено: {stats['assigned']}\n"
            f"• 🟢 Активно: {stats['active']}\n"
            f"• 📦 Погрузка: {stats['loading']}\n"
            f"• 🚚 В пути: {stats['in_transit']}\n"
            f"• 📥 Выгрузка: {stats['unloading']}\n"
            f"• ✅ Завершено: {stats['completed']}\n"
            f"• 📌 Всего: {stats['total']}\n\n"
            f"Выберите действие:",
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Failed to show admin panel: {e}", exc_info=True)
        await message.answer(
            "❌ Ошибка загрузки панели управления.\n"
            "Попробуйте позже."
        )


@router.message(Command("trips"))
async def list_trips_command(message: Message):
    """
    Список всех рейсов (только для кураторов).

    Использование: /trips
    """
    if not is_curator(message.from_user.id):
        await message.answer("❌ Эта команда доступна только кураторам")
        return

    try:
        # Получаем активные рейсы (не завершенные)
        all_trips = await db_trips.get_all_trips(limit=50)
        active_trips = [t for t in all_trips if t['status'] not in ['completed', 'cancelled']]

        if not active_trips:
            kb = InlineKeyboardBuilder()
            kb.button(text="➕ Создать рейс", callback_data="new_trip")

            await message.answer(
                "📋 <b>Активные рейсы</b>\n\n"
                "Нет активных рейсов.\n\n"
                "Используйте /create_trip для создания нового рейса.",
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
            return

        # Формируем список
        text = "📋 <b>Активные рейсы:</b>\n\n"

        status_emoji = {
            'assigned': '⏳',
            'active': '🟢',
            'loading': '📦',
            'in_transit': '🚚',
            'unloading': '📥',
            'completed': '✅'
        }

        for trip in active_trips[:10]:
            emoji = status_emoji.get(trip['status'], '❓')
            text += (
                f"{emoji} <b>{trip['trip_number']}</b> - {trip['phone']}\n"
                f"   {trip['loading_address'][:30]}...\n"
                f"   ↓\n"
                f"   {trip['unloading_address'][:30]}...\n\n"
            )

        if len(active_trips) > 10:
            text += f"\n... и еще {len(active_trips) - 10} рейсов"

        # Кнопки для навигации
        kb = InlineKeyboardBuilder()
        for trip in active_trips[:6]:
            kb.button(
                text=f"📋 {trip['trip_number']}",
                callback_data=f"view_trip:{trip['trip_id']}"
            )

        kb.button(text="➕ Создать рейс", callback_data="new_trip")
        kb.button(text="🔄 Обновить", callback_data="list_active_trips")
        kb.adjust(2, 2, 2, 1, 1)

        await message.answer(
            text,
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Failed to list trips: {e}", exc_info=True)
        await message.answer("❌ Ошибка загрузки списка рейсов")


@router.message(Command("create_trip"))
async def start_create_trip(message: Message, state: FSMContext):
    """
    Начало создания рейса (только для кураторов).

    Использование: /create_trip
    """
    if not is_curator(message.from_user.id):
        await message.answer("❌ Эта команда доступна только кураторам")
        return

    await state.set_state(CreateTripStates.waiting_data)

    await message.answer(
        "➕ <b>Создание рейса</b>\n\n"
        "Отправьте данные одним сообщением (6 строк):\n\n"
        "1️⃣ Телефон водителя\n"
        "2️⃣ Адрес загрузки\n"
        "3️⃣ Адрес выгрузки\n"
        "4️⃣ Дата загрузки (ДД.ММ)\n"
        "5️⃣ Дата выгрузки (ДД.ММ)\n"
        "6️⃣ Ставка\n\n"
        "<b>Пример:</b>\n"
        "<code>+79991234567\n"
        "Москва, ул. Ленина 1\n"
        "Санкт-Петербург, пр. Невский 10\n"
        "20.11\n"
        "21.11\n"
        "50000</code>",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )


@router.message(CreateTripStates.waiting_data)
async def process_trip_data(message: Message, state: FSMContext):
    """Обработка данных для создания рейса."""

    # Парсим данные
    lines = [line.strip() for line in message.text.split("\n") if line.strip()]

    if len(lines) != 6:
        await message.answer(
            "❌ Неверный формат!\n\n"
            "Должно быть ровно 6 строк:\n"
            "1. Телефон водителя\n"
            "2. Адрес загрузки\n"
            "3. Адрес выгрузки\n"
            "4. Дата загрузки\n"
            "5. Дата выгрузки\n"
            "6. Ставка\n\n"
            "Попробуйте еще раз или /cancel"
        )
        return

    phone = lines[0]
    loading_address = lines[1]
    unloading_address = lines[2]
    loading_date = lines[3]
    unloading_date = lines[4]
    rate = lines[5]

    # Валидация телефона
    if not phone.startswith("+7") or len(phone) != 12:
        await message.answer(
            "❌ Неверный формат телефона!\n"
            "Должно быть: +79991234567\n\n"
            "Попробуйте еще раз или /cancel"
        )
        return

    # Валидация и форматирование дат
    try:
        current_year = datetime.now().year
        loading_date_full = f"{loading_date}.{current_year}"
        unloading_date_full = f"{unloading_date}.{current_year}"

        # Проверяем формат
        datetime.strptime(loading_date_full, "%d.%m.%Y")
        datetime.strptime(unloading_date_full, "%d.%m.%Y")
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты!\n"
            "Должно быть: ДД.ММ (например: 20.11)\n\n"
            "Попробуйте еще раз или /cancel"
        )
        return

    # Валидация ставки
    try:
        rate_float = float(rate.replace(" ", "").replace(",", "."))
    except ValueError:
        await message.answer(
            "❌ Ставка должна быть числом!\n"
            "Например: 50000 или 50000.50\n\n"
            "Попробуйте еще раз или /cancel"
        )
        return

    # Проверяем, есть ли водитель в системе
    user_id = await get_user_id_by_phone(phone)

    # Создаем рейс
    try:
        trip_id, trip_number = await db_trips.create_trip_by_curator(
            phone=phone,
            loading_address=loading_address,
            loading_date=loading_date_full,
            unloading_address=unloading_address,
            unloading_date=unloading_date_full,
            rate=rate_float,
            curator_id=message.from_user.id
        )

        await state.clear()

        # Формируем клавиатуру
        kb = InlineKeyboardBuilder()
        kb.button(text="✏️ Редактировать", callback_data=f"edit_trip:{trip_id}")

        if user_id:
            kb.button(text="🚀 Активировать", callback_data=f"activate_trip:{trip_id}")

        kb.button(text="🗑 Удалить", callback_data=f"delete_trip:{trip_id}")
        kb.button(text="◀️ Список рейсов", callback_data="list_trips")
        kb.adjust(1, 1, 1, 1)

        # Определяем статус
        if user_id:
            status_text = "⏳ Ожидает активации водителем"
            warning = ""
        else:
            status_text = "⚠️ Водитель не зарегистрирован в боте"
            warning = "\n\n⚠️ Водитель должен запустить бота и поделиться номером."

        # Отправляем куратору
        await message.answer(
            f"✅ <b>Рейс создан!</b>\n\n"
            f"🚚 Рейс <b>#{trip_number}</b>\n"
            f"📞 Водитель: {phone}\n"
            f"📍 {loading_address}\n"
            f"     ↓\n"
            f"📍 {unloading_address}\n"
            f"📅 {loading_date} → {unloading_date}\n"
            f"💰 {rate_float:,.0f} ₽\n\n"
            f"Статус: {status_text}"
            f"{warning}",
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )

        # Уведомляем в группу кураторов
        if GROUP_CHAT_ID:
            try:
                await message.bot.send_message(
                    GROUP_CHAT_ID,
                    f"🆕 <b>Создан новый рейс</b>\n\n"
                    f"🚚 Рейс #{trip_number}\n"
                    f"📞 {phone}\n"
                    f"📍 {loading_address} → {unloading_address}\n"
                    f"📅 {loading_date} → {unloading_date}\n"
                    f"💰 {rate_float:,.0f} ₽\n\n"
                    f"Куратор: {message.from_user.full_name}",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Failed to send notification to group: {e}")

    except Exception as e:
        logger.error(f"Failed to create trip: {e}", exc_info=True)
        await message.answer(
            f"❌ Ошибка создания рейса:\n{str(e)}\n\n"
            f"Попробуйте еще раз или /cancel"
        )
        await state.clear()


@router.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    """Отмена текущего действия."""
    await state.clear()
    await callback.message.edit_text("❌ Отменено")
    await callback.answer()


@router.callback_query(F.data.startswith("activate_trip:"))
async def activate_trip_callback(callback: CallbackQuery):
    """Активация рейса куратором вручную."""
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    trip_id = int(callback.data.split(":")[1])

    try:
        trip = await db_trips.get_trip(trip_id)
        if not trip:
            await callback.answer("❌ Рейс не найден", show_alert=True)
            return

        # Проверяем статус
        if trip['status'] != 'assigned':
            await callback.answer(
                f"❌ Рейс уже активирован (статус: {trip['status']})",
                show_alert=True
            )
            return

        # Активируем
        await db_trips.activate_trip(trip_id, callback.from_user.id)

        # Обновляем сообщение
        kb = InlineKeyboardBuilder()
        kb.button(text="✏️ Редактировать", callback_data=f"edit_trip:{trip_id}")
        kb.button(text="📋 Открыть", callback_data=f"view_trip:{trip_id}")
        kb.button(text="◀️ Назад", callback_data="list_trips")
        kb.adjust(2, 1)

        await callback.message.edit_text(
            f"✅ <b>Рейс активирован!</b>\n\n"
            f"🚚 Рейс #{trip['trip_number']}\n"
            f"📞 {trip['phone']}\n"
            f"📍 {trip['loading_address']} → {trip['unloading_address']}\n"
            f"📅 {trip['loading_date']} → {trip['unloading_date']}\n"
            f"💰 {trip['rate']:,.0f} ₽\n\n"
            f"Статус: 🟢 Активен\n"
            f"Уведомление отправлено водителю.",
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )

        # Отправляем уведомление водителю
        if trip['user_id'] and trip['user_id'] > 0:
            try:
                await callback.bot.send_message(
                    trip['user_id'],
                    f"🚚 <b>Ваш рейс активирован куратором!</b>\n\n"
                    f"Рейс #{trip['trip_number']}\n"
                    f"📍 {trip['loading_address']}\n"
                    f"     ↓\n"
                    f"📍 {trip['unloading_address']}\n"
                    f"📅 Погрузка: {trip['loading_date']}\n"
                    f"📅 Выгрузка: {trip['unloading_date']}\n"
                    f"💰 Ставка: {trip['rate']:,.0f} ₽\n\n"
                    f"Не забывайте делиться местоположением!",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Failed to notify driver: {e}")

        await callback.answer("✅ Рейс активирован!")

    except Exception as e:
        logger.error(f"Failed to activate trip: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("view_trip:"))
async def view_trip_callback(callback: CallbackQuery):
    """Просмотр детальной информации о рейсе."""
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    trip_id = int(callback.data.split(":")[1])

    try:
        trip = await db_trips.get_trip(trip_id)
        if not trip:
            await callback.answer("❌ Рейс не найден", show_alert=True)
            return

        # Получаем последнюю локацию
        from db import get_last_point
        last_loc = await get_last_point(trip['user_id']) if trip['user_id'] else None

        if last_loc:
            from datetime import datetime
            last_time = datetime.fromisoformat(last_loc['ts'])
            now = datetime.now()
            delta = now - last_time

            if delta.total_seconds() < 3600:
                loc_text = f"{int(delta.total_seconds() / 60)} мин назад"
            elif delta.total_seconds() < 86400:
                loc_text = f"{int(delta.total_seconds() / 3600)} ч назад"
            else:
                loc_text = f"{int(delta.total_seconds() / 86400)} дн назад"
        else:
            loc_text = "нет данных"

        # Статус эмодзи
        status_map = {
            'assigned': '⏳ Ожидает активации',
            'active': '🟢 Активен',
            'loading': '📦 Погрузка',
            'in_transit': '🚚 В пути',
            'unloading': '📥 Выгрузка',
            'completed': '✅ Завершен'
        }
        status_text = status_map.get(trip['status'], trip['status'])

        # Формируем кнопки
        kb = InlineKeyboardBuilder()
        kb.button(text="✏️ Редактировать", callback_data=f"edit_trip:{trip_id}")
        kb.button(text="📍 Запросить место", callback_data=f"request_location:{trip_id}")

        if trip['status'] not in ['completed', 'cancelled']:
            kb.button(text="✅ Завершить", callback_data=f"complete_trip:{trip_id}")

        kb.button(text="📋 История", callback_data=f"trip_history:{trip_id}")
        kb.button(text="◀️ Назад", callback_data="list_trips")
        kb.adjust(2, 1, 1, 1)

        await callback.message.edit_text(
            f"🚚 <b>Рейс #{trip['trip_number']}</b>\n"
            f"{status_text}\n\n"
            f"📞 Водитель: {trip['phone']}\n"
            f"📍 {trip['loading_address']}\n"
            f"     ↓\n"
            f"📍 {trip['unloading_address']}\n"
            f"📅 {trip['loading_date']} → {trip['unloading_date']}\n"
            f"💰 Ставка: {trip['rate']:,.0f} ₽\n\n"
            f"📍 Последняя локация: {loc_text}\n"
            f"🕐 Создан: {trip['created_at'][:10]}",
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Failed to view trip: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("request_location:"))
async def request_location_callback(callback: CallbackQuery):
    """Запрос местоположения у водителя."""
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    trip_id = int(callback.data.split(":")[1])

    try:
        trip = await db_trips.get_trip(trip_id)
        if not trip:
            await callback.answer("❌ Рейс не найден", show_alert=True)
            return

        if not trip['user_id'] or trip['user_id'] == 0:
            await callback.answer(
                "❌ Водитель еще не зарегистрирован в боте",
                show_alert=True
            )
            return

        # Формируем кнопки подтверждения
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Отправить", callback_data=f"confirm_location:{trip_id}")
        kb.button(text="❌ Отмена", callback_data=f"view_trip:{trip_id}")
        kb.adjust(1, 1)

        await callback.message.edit_text(
            f"📍 <b>Запрос местоположения</b>\n\n"
            f"Отправить водителю напоминание\n"
            f"о необходимости поделиться\n"
            f"местоположением?\n\n"
            f"📞 {trip['phone']}\n"
            f"🚚 Рейс #{trip['trip_number']}",
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Failed to request location: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("confirm_location:"))
async def confirm_location_callback(callback: CallbackQuery):
    """Подтверждение отправки запроса местоположения."""
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    trip_id = int(callback.data.split(":")[1])

    try:
        trip = await db_trips.get_trip(trip_id)
        if not trip or not trip['user_id']:
            await callback.answer("❌ Ошибка", show_alert=True)
            return

        # Отправляем водителю
        from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
        from aiogram.utils.keyboard import ReplyKeyboardBuilder

        kb = ReplyKeyboardBuilder()
        kb.button(text="📍 Поделиться местоположением", request_location=True)
        kb.adjust(1)

        await callback.bot.send_message(
            trip['user_id'],
            f"📍 <b>Напоминание от куратора</b>\n\n"
            f"Пожалуйста, поделитесь текущим местоположением.\n\n"
            f"🚚 Рейс #{trip['trip_number']}",
            reply_markup=kb.as_markup(resize_keyboard=True),
            parse_mode="HTML"
        )

        # Логируем событие
        await db_trips.log_trip_event(
            trip_id=trip_id,
            event_type="location_requested",
            description="Куратор запросил местоположение",
            created_by=callback.from_user.id
        )

        # Возвращаемся к карточке рейса
        await view_trip_callback(callback)
        await callback.answer("✅ Запрос отправлен водителю")

    except Exception as e:
        logger.error(f"Failed to send location request: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("complete_trip:"))
async def complete_trip_callback(callback: CallbackQuery):
    """Завершение рейса куратором."""
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    trip_id = int(callback.data.split(":")[1])

    try:
        trip = await db_trips.get_trip(trip_id)
        if not trip:
            await callback.answer("❌ Рейс не найден", show_alert=True)
            return

        # Кнопки подтверждения
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Да, завершить", callback_data=f"confirm_complete:{trip_id}")
        kb.button(text="❌ Отмена", callback_data=f"view_trip:{trip_id}")
        kb.adjust(1, 1)

        await callback.message.edit_text(
            f"⚠️ <b>Завершение рейса #{trip['trip_number']}</b>\n\n"
            f"📞 Водитель: {trip['phone']}\n"
            f"📍 {trip['loading_address']} → {trip['unloading_address']}\n\n"
            f"Завершить рейс?",
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Failed to prepare completion: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("confirm_complete:"))
async def confirm_complete_callback(callback: CallbackQuery):
    """Подтверждение завершения рейса."""
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    trip_id = int(callback.data.split(":")[1])

    try:
        trip = await db_trips.get_trip(trip_id)
        if not trip:
            await callback.answer("❌ Рейс не найден", show_alert=True)
            return

        # Завершаем рейс
        await db_trips.update_trip_status(trip_id, 'completed', callback.from_user.id)

        # Уведомляем куратора
        await callback.message.edit_text(
            f"✅ <b>Рейс #{trip['trip_number']} завершен!</b>\n\n"
            f"Уведомление отправлено водителю.\n"
            f"Отслеживание остановлено.",
            parse_mode="HTML"
        )

        # Уведомляем водителя
        if trip['user_id'] and trip['user_id'] > 0:
            try:
                await callback.bot.send_message(
                    trip['user_id'],
                    f"✅ <b>Рейс #{trip['trip_number']} завершен!</b>\n\n"
                    f"Спасибо за работу! 🎉\n\n"
                    f"Отслеживание местоположения остановлено.\n"
                    f"При получении нового рейса вы получите уведомление.",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Failed to notify driver: {e}")

        await callback.answer("✅ Рейс завершен!")

    except Exception as e:
        logger.error(f"Failed to complete trip: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(F.data == "list_trips")
async def list_trips_callback(callback: CallbackQuery):
    """Показать список всех рейсов."""
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    try:
        # Получаем все рейсы
        all_trips = await db_trips.get_all_trips(limit=50)

        if not all_trips:
            kb = InlineKeyboardBuilder()
            kb.button(text="➕ Создать рейс", callback_data="new_trip")
            kb.button(text="◀️ Назад", callback_data="back_to_admin")

            await callback.message.edit_text(
                "📋 <b>Все рейсы</b>\n\n"
                "Нет рейсов.\n\n"
                "Используйте /create_trip для создания нового рейса.",
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
            await callback.answer()
            return

        # Формируем список
        text = "📊 <b>Все рейсы</b> (последние 10):\n\n"

        status_emoji = {
            'assigned': '⏳',
            'active': '🟢',
            'loading': '📦',
            'in_transit': '🚚',
            'unloading': '📥',
            'completed': '✅'
        }

        for trip in all_trips[:10]:
            emoji = status_emoji.get(trip['status'], '❓')
            text += (
                f"{emoji} <b>{trip['trip_number']}</b> - {trip['phone']}\n"
                f"   {trip['loading_address'][:30]}...\n"
                f"   ↓\n"
                f"   {trip['unloading_address'][:30]}...\n\n"
            )

        if len(all_trips) > 10:
            text += f"\n... и еще {len(all_trips) - 10} рейсов"

        # Кнопки для навигации
        kb = InlineKeyboardBuilder()
        for trip in all_trips[:6]:
            kb.button(
                text=f"📋 {trip['trip_number']}",
                callback_data=f"view_trip:{trip['trip_id']}"
            )

        kb.button(text="◀️ Назад", callback_data="back_to_admin")
        kb.adjust(2, 2, 2, 1)

        await callback.message.edit_text(
            text,
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Failed to list trips: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(F.data == "list_active_trips")
async def list_active_trips_callback(callback: CallbackQuery):
    """Показать список активных рейсов."""
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    try:
        # Получаем активные рейсы (не завершенные)
        all_trips = await db_trips.get_all_trips(limit=100)
        active_trips = [t for t in all_trips if t['status'] not in ['completed', 'cancelled']]

        if not active_trips:
            kb = InlineKeyboardBuilder()
            kb.button(text="➕ Создать рейс", callback_data="new_trip")
            kb.button(text="◀️ Назад", callback_data="back_to_admin")

            await callback.message.edit_text(
                "📋 <b>Активные рейсы</b>\n\n"
                "Нет активных рейсов.\n\n"
                "Используйте /create_trip для создания нового рейса.",
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
            await callback.answer()
            return

        # Формируем список
        text = "📋 <b>Активные рейсы:</b>\n\n"

        status_emoji = {
            'assigned': '⏳',
            'active': '🟢',
            'loading': '📦',
            'in_transit': '🚚',
            'unloading': '📥',
        }

        for trip in active_trips[:10]:
            emoji = status_emoji.get(trip['status'], '❓')
            text += (
                f"{emoji} <b>{trip['trip_number']}</b> - {trip['phone']}\n"
                f"   {trip['loading_address'][:30]}...\n"
                f"   ↓\n"
                f"   {trip['unloading_address'][:30]}...\n\n"
            )

        if len(active_trips) > 10:
            text += f"\n... и еще {len(active_trips) - 10} рейсов"

        # Кнопки для навигации
        kb = InlineKeyboardBuilder()
        for trip in active_trips[:6]:
            kb.button(
                text=f"📋 {trip['trip_number']}",
                callback_data=f"view_trip:{trip['trip_id']}"
            )

        kb.button(text="🔄 Обновить", callback_data="list_active_trips")
        kb.button(text="◀️ Назад", callback_data="back_to_admin")
        kb.adjust(2, 2, 2, 1, 1)

        await callback.message.edit_text(
            text,
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Failed to list active trips: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(F.data == "list_completed_trips")
async def list_completed_trips_callback(callback: CallbackQuery):
    """Показать список завершенных рейсов."""
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    try:
        # Получаем завершенные рейсы
        all_trips = await db_trips.get_all_trips(limit=100)
        completed_trips = [t for t in all_trips if t['status'] == 'completed']

        if not completed_trips:
            kb = InlineKeyboardBuilder()
            kb.button(text="◀️ Назад", callback_data="back_to_admin")

            await callback.message.edit_text(
                "✅ <b>Завершенные рейсы</b>\n\n"
                "Нет завершенных рейсов.",
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
            await callback.answer()
            return

        # Формируем список
        text = "✅ <b>Завершенные рейсы</b> (последние 10):\n\n"

        for trip in completed_trips[:10]:
            completed_date = trip.get('completed_at', '')[:10] if trip.get('completed_at') else 'н/д'
            text += (
                f"✅ <b>{trip['trip_number']}</b> - {trip['phone']}\n"
                f"   {trip['loading_address'][:30]}... → {trip['unloading_address'][:30]}...\n"
                f"   Завершен: {completed_date}\n\n"
            )

        if len(completed_trips) > 10:
            text += f"\n... и еще {len(completed_trips) - 10} рейсов"

        # Кнопки для навигации
        kb = InlineKeyboardBuilder()
        for trip in completed_trips[:6]:
            kb.button(
                text=f"✅ {trip['trip_number']}",
                callback_data=f"view_trip:{trip['trip_id']}"
            )

        kb.button(text="◀️ Назад", callback_data="back_to_admin")
        kb.adjust(2, 2, 2, 1)

        await callback.message.edit_text(
            text,
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Failed to list completed trips: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(F.data == "back_to_admin")
async def back_to_admin_callback(callback: CallbackQuery):
    """Вернуться к админ-панели."""
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    try:
        all_trips = await db_trips.get_all_trips(limit=1000)

        # Считаем по статусам
        stats = {
            'assigned': 0,
            'active': 0,
            'loading': 0,
            'in_transit': 0,
            'unloading': 0,
            'completed': 0,
            'total': len(all_trips)
        }

        for trip in all_trips:
            status = trip.get('status', 'unknown')
            if status in stats:
                stats[status] += 1

        # Формируем админ-панель
        kb = InlineKeyboardBuilder()
        kb.button(text="➕ Создать рейс", callback_data="new_trip")
        kb.button(text="📋 Активные рейсы", callback_data="list_active_trips")
        kb.button(text="📊 Все рейсы", callback_data="list_trips")
        kb.button(text="✅ Завершенные", callback_data="list_completed_trips")
        kb.button(text="📈 Статистика", callback_data="show_stats")
        kb.adjust(1, 2, 2, 1)

        await callback.message.edit_text(
            "🎛 <b>Панель управления рейсами</b>\n\n"
            f"📊 Статистика:\n"
            f"• ⏳ Назначено: {stats['assigned']}\n"
            f"• 🟢 Активно: {stats['active']}\n"
            f"• 📦 Погрузка: {stats['loading']}\n"
            f"• 🚚 В пути: {stats['in_transit']}\n"
            f"• 📥 Разгрузка: {stats['unloading']}\n"
            f"• ✅ Завершено: {stats['completed']}\n\n"
            f"🔢 Всего рейсов: {stats['total']}",
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Failed to show admin panel: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(F.data == "new_trip")
async def new_trip_callback(callback: CallbackQuery, state: FSMContext):
    """Создать новый рейс через callback."""
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    # Запускаем процесс создания рейса
    await state.set_state(CreateTripStates.waiting_data)

    await callback.message.answer(
        "➕ <b>Создание рейса</b>\n\n"
        "Отправьте данные одним сообщением (6 строк):\n\n"
        "1️⃣ Телефон водителя\n"
        "2️⃣ Адрес загрузки\n"
        "3️⃣ Адрес выгрузки\n"
        "4️⃣ Дата загрузки (ДД.ММ)\n"
        "5️⃣ Дата выгрузки (ДД.ММ)\n"
        "6️⃣ Ставка\n\n"
        "<b>Пример:</b>\n"
        "<code>+79991234567\n"
        "Москва, ул. Ленина 1\n"
        "Санкт-Петербург, пр. Невский 10\n"
        "20.11\n"
        "21.11\n"
        "50000</code>",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("trip_history:"))
async def trip_history_callback(callback: CallbackQuery):
    """Показать историю рейса."""
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    trip_id = int(callback.data.split(":")[1])

    try:
        trip = await db_trips.get_trip(trip_id)
        if not trip:
            await callback.answer("❌ Рейс не найден", show_alert=True)
            return

        # Получаем события
        events = await db_trips.get_trip_events(trip_id, limit=10)

        text = f"📋 <b>История рейса #{trip['trip_number']}</b>\n\n"

        if not events:
            text += "Нет событий"
        else:
            for event in events:
                created_at = event['created_at'][:16].replace('T', ' ')
                text += f"• {created_at} - {event['description']}\n"

        # Кнопка назад
        kb = InlineKeyboardBuilder()
        kb.button(text="◀️ Назад", callback_data=f"view_trip:{trip_id}")

        await callback.message.edit_text(
            text,
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Failed to show history: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


# ============================================================================
# Обработчики текстовых кнопок с клавиатуры куратора
# ============================================================================

@router.message(F.text == "➕ Создать рейс")
async def text_create_trip(message: Message, state: FSMContext):
    """Обработчик текстовой кнопки 'Создать рейс'."""
    if not is_curator(message.from_user.id):
        return
    # Перенаправляем на команду /create_trip
    await start_create_trip(message, state)


@router.message(F.text == "📋 Активные рейсы")
async def text_list_trips(message: Message):
    """Обработчик текстовой кнопки 'Активные рейсы'."""
    if not is_curator(message.from_user.id):
        return
    # Перенаправляем на команду /trips
    await list_trips_command(message)


@router.message(F.text == "🎛 Панель управления")
async def text_admin_panel(message: Message):
    """Обработчик текстовой кнопки 'Панель управления'."""
    if not is_curator(message.from_user.id):
        return
    # Перенаправляем на команду /admin
    await admin_panel(message)


# ============================================================================
# Обработчик редактирования рейса
# ============================================================================

@router.callback_query(F.data.startswith("edit_trip:"))
async def edit_trip_callback(callback: CallbackQuery):
    """Меню редактирования рейса."""
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    trip_id = int(callback.data.split(":")[1])

    try:
        trip = await db_trips.get_trip(trip_id)
        if not trip:
            await callback.answer("❌ Рейс не найден", show_alert=True)
            return

        # Формируем меню редактирования
        kb = InlineKeyboardBuilder()
        kb.button(text="📞 Изменить телефон", callback_data=f"edit_field:phone:{trip_id}")
        kb.button(text="📍 Изменить адреса", callback_data=f"edit_field:addresses:{trip_id}")
        kb.button(text="📅 Изменить даты", callback_data=f"edit_field:dates:{trip_id}")
        kb.button(text="💰 Изменить ставку", callback_data=f"edit_field:rate:{trip_id}")
        kb.button(text="◀️ Назад", callback_data=f"view_trip:{trip_id}")
        kb.adjust(1)

        await callback.message.edit_text(
            f"✏️ <b>Редактирование рейса #{trip['trip_number']}</b>\n\n"
            f"📞 Телефон: {trip['phone']}\n"
            f"📍 Загрузка: {trip['loading_address']}\n"
            f"📍 Выгрузка: {trip['unloading_address']}\n"
            f"📅 Даты: {trip['loading_date']} → {trip['unloading_date']}\n"
            f"💰 Ставка: {trip['rate']:,.0f} ₽\n\n"
            f"Выберите, что хотите изменить:",
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Failed to show edit menu: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("edit_field:"))
async def edit_field_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования конкретного поля."""
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    parts = callback.data.split(":")
    field = parts[1]
    trip_id = int(parts[2])

    # Сохраняем trip_id в state
    await state.update_data(edit_trip_id=trip_id, edit_field=field)

    # Показываем инструкцию в зависимости от поля
    instructions = {
        "phone": "📞 Отправьте новый номер телефона в формате:\n<code>+79991234567</code>",
        "addresses": "📍 Отправьте новые адреса в формате:\n<code>Адрес загрузки\nАдрес выгрузки</code>",
        "dates": "📅 Отправьте новые даты в формате:\n<code>ДД.ММ\nДД.ММ</code>\n(дата загрузки и дата выгрузки)",
        "rate": "💰 Отправьте новую ставку (только число):\n<code>50000</code>"
    }

    await callback.message.answer(
        f"✏️ <b>Редактирование</b>\n\n{instructions[field]}\n\n"
        f"Или /cancel для отмены",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )

    # Устанавливаем состояние ожидания
    state_map = {
        "phone": EditTripStates.waiting_phone,
        "addresses": EditTripStates.waiting_addresses,
        "dates": EditTripStates.waiting_dates,
        "rate": EditTripStates.waiting_rate
    }
    await state.set_state(state_map[field])
    await callback.answer()


@router.message(EditTripStates.waiting_phone)
async def process_edit_phone(message: Message, state: FSMContext):
    """Обработка нового номера телефона."""
    phone = message.text.strip()

    # Валидация
    if not phone.startswith("+7") or len(phone) != 12:
        await message.answer("❌ Неверный формат! Используйте: +79991234567")
        return

    data = await state.get_data()
    trip_id = data.get("edit_trip_id")

    try:
        await db_trips.update_trip_phone(trip_id, phone)
        await state.clear()
        await message.answer(
            f"✅ Телефон обновлен на {phone}!\n\n"
            f"Используйте /trips для просмотра рейсов."
        )
    except Exception as e:
        logger.error(f"Failed to update phone: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.message(EditTripStates.waiting_addresses)
async def process_edit_addresses(message: Message, state: FSMContext):
    """Обработка новых адресов."""
    lines = [line.strip() for line in message.text.split("\n") if line.strip()]

    if len(lines) != 2:
        await message.answer("❌ Должно быть 2 строки:\n1. Адрес загрузки\n2. Адрес выгрузки")
        return

    loading_address = lines[0]
    unloading_address = lines[1]

    data = await state.get_data()
    trip_id = data.get("edit_trip_id")

    try:
        await db_trips.update_trip_addresses(trip_id, loading_address, unloading_address)
        await state.clear()
        await message.answer(
            f"✅ Адреса обновлены!\n\n"
            f"📍 {loading_address}\n"
            f"📍 {unloading_address}\n\n"
            f"Используйте /trips для просмотра рейсов."
        )
    except Exception as e:
        logger.error(f"Failed to update addresses: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.message(EditTripStates.waiting_dates)
async def process_edit_dates(message: Message, state: FSMContext):
    """Обработка новых дат."""
    lines = [line.strip() for line in message.text.split("\n") if line.strip()]

    if len(lines) != 2:
        await message.answer("❌ Должно быть 2 строки с датами в формате ДД.ММ")
        return

    loading_date = lines[0]
    unloading_date = lines[1]

    # Валидация дат
    try:
        from datetime import datetime
        current_year = datetime.now().year
        datetime.strptime(f"{loading_date}.{current_year}", "%d.%m.%Y")
        datetime.strptime(f"{unloading_date}.{current_year}", "%d.%m.%Y")
    except ValueError:
        await message.answer("❌ Неверный формат даты! Используйте ДД.ММ (например: 20.11)")
        return

    data = await state.get_data()
    trip_id = data.get("edit_trip_id")

    try:
        await db_trips.update_trip_dates(trip_id, loading_date, unloading_date)
        await state.clear()
        await message.answer(
            f"✅ Даты обновлены!\n\n"
            f"📅 {loading_date} → {unloading_date}\n\n"
            f"Используйте /trips для просмотра рейсов."
        )
    except Exception as e:
        logger.error(f"Failed to update dates: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.message(EditTripStates.waiting_rate)
async def process_edit_rate(message: Message, state: FSMContext):
    """Обработка новой ставки."""
    try:
        rate = float(message.text.strip().replace(" ", "").replace(",", "."))
    except ValueError:
        await message.answer("❌ Неверный формат! Введите число (например: 50000)")
        return

    data = await state.get_data()
    trip_id = data.get("edit_trip_id")

    try:
        await db_trips.update_trip_rate(trip_id, rate)
        await state.clear()
        await message.answer(
            f"✅ Ставка обновлена на {rate:,.0f} ₽!\n\n"
            f"Используйте /trips для просмотра рейсов."
        )
    except Exception as e:
        logger.error(f"Failed to update rate: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка: {str(e)}")

