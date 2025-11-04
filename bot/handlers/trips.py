"""
Обработчик управления рейсами для водителей.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from datetime import datetime
from dateutil.parser import isoparse
import logging

import db_trips
from db import get_phone

router = Router()
logger = logging.getLogger(__name__)


def trip_management_kb(trip_id: int) -> InlineKeyboardMarkup:
    """
    Inline-клавиатура для управления рейсом.

    Args:
        trip_id: ID рейса

    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками действий
    """
    kb = InlineKeyboardBuilder()

    kb.button(text="📸 Фото погрузки", callback_data=f"trip:{trip_id}:loading_photo")
    kb.button(text="📸 Фото выгрузки", callback_data=f"trip:{trip_id}:unloading_photo")
    kb.button(text="📄 Документы", callback_data=f"trip:{trip_id}:documents")
    kb.button(text="❗ Проблема", callback_data=f"trip:{trip_id}:issue")
    kb.button(text="ℹ️ Детали", callback_data=f"trip:{trip_id}:details")

    kb.adjust(2, 2, 1)
    return kb.as_markup()


def get_trip_progress(status: str) -> str:
    """
    Визуализация прогресса рейса с эмодзи.

    Args:
        status: Текущий статус рейса

    Returns:
        str: Строка с прогресс-баром
    """
    stages = {
        'created': 0,
        'loading': 1,
        'in_transit': 2,
        'unloading': 3,
        'completed': 4
    }

    current_stage = stages.get(status, 0)

    filled = ['🟢'] * (current_stage + 1)
    empty = ['⚪'] * (4 - current_stage)

    progress = ''.join(filled + empty)

    status_names = {
        'created': 'Создан',
        'loading': 'Погрузка',
        'in_transit': 'В пути',
        'unloading': 'Выгрузка',
        'completed': 'Завершён'
    }

    return f"{progress} {status_names.get(status, status)}"


def format_trip_card(trip: dict) -> str:
    """
    Форматировать карточку рейса для отображения.

    Args:
        trip: Словарь с данными рейса

    Returns:
        str: Отформатированная карточка рейса
    """
    # Форматирование дат
    loading_date = "не указана"
    unloading_date = "не указана"

    if trip.get('loading_date'):
        try:
            dt = isoparse(trip['loading_date'])
            loading_date = dt.strftime('%d.%m.%Y')
        except:
            loading_date = trip['loading_date']

    if trip.get('unloading_date'):
        try:
            dt = isoparse(trip['unloading_date'])
            unloading_date = dt.strftime('%d.%m.%Y')
        except:
            unloading_date = trip['unloading_date']

    # Прогресс
    progress = get_trip_progress(trip['status'])

    # Формирование карточки
    card = (
        f"🚚 **Рейс #{trip['trip_number']}**\n"
        f"{progress}\n\n"
        f"📍 **Маршрут:**\n"
        f"   Погрузка: {trip.get('loading_address', 'не указан')} ({loading_date})\n"
        f"   Выгрузка: {trip.get('unloading_address', 'не указан')} ({unloading_date})\n\n"
        f"📦 **Груз:** {trip.get('cargo_type', 'не указан')}\n"
        f"💰 **Ставка:** {trip.get('rate', 0):,.0f} ₽\n"
    )

    return card


@router.message(Command("trips"))
@router.message(F.text == "Мои рейсы")
@router.message(F.text == "📋 Мои рейсы")
async def show_my_trips(message: Message):
    """Показать активные рейсы водителя."""
    user_id = message.from_user.id

    try:
        trips = await db_trips.get_user_active_trips(user_id)
    except Exception as e:
        logger.error(f"Failed to get trips for user {user_id}: {e}")
        await message.answer("❌ Ошибка при получении списка рейсов")
        return

    if not trips:
        await message.answer(
            "У вас пока нет активных рейсов.\n\n"
            "Рейсы назначаются куратором через систему управления."
        )
        return

    await message.answer(f"📋 **Ваши активные рейсы:** ({len(trips)})")

    for trip in trips:
        card = format_trip_card(trip)
        await message.answer(
            card,
            reply_markup=trip_management_kb(trip['trip_id']),
            parse_mode="Markdown"
        )


@router.callback_query(F.data.startswith("trip:"))
async def handle_trip_action(callback: CallbackQuery):
    """Обработчик действий с рейсом."""
    # Парсим callback_data: "trip:123:action"
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("❌ Ошибка формата")
        return

    trip_id = int(parts[1])
    action = parts[2]

    # Получаем информацию о рейсе
    try:
        trip = await db_trips.get_trip(trip_id)
    except Exception as e:
        logger.error(f"Failed to get trip {trip_id}: {e}")
        await callback.answer("❌ Ошибка получения рейса")
        return

    if not trip:
        await callback.answer("❌ Рейс не найден")
        return

    # Обрабатываем действие
    if action == "loading_photo":
        await callback.message.answer(
            f"📸 Отправьте фото погрузки для рейса #{trip['trip_number']}\n\n"
            "Используйте кнопку '📤 Отправить документы' → 'Фото погрузки'"
        )
        await callback.answer()

    elif action == "unloading_photo":
        await callback.message.answer(
            f"📸 Отправьте фото выгрузки для рейса #{trip['trip_number']}\n\n"
            "Используйте кнопку '📤 Отправить документы' → 'Фото выгрузки'"
        )
        await callback.answer()

    elif action == "documents":
        await callback.message.answer(
            f"📄 Отправьте документы для рейса #{trip['trip_number']}\n\n"
            "Используйте кнопку '📤 Отправить документы'"
        )
        await callback.answer()

    elif action == "issue":
        await callback.message.answer(
            f"❗ Опишите проблему по рейсу #{trip['trip_number']}\n\n"
            "Ваше сообщение будет отправлено куратору."
        )
        await callback.answer()

        # TODO: В будущем можно добавить FSM для сбора описания проблемы

    elif action == "details":
        # Показать детальную информацию
        try:
            events = await db_trips.get_trip_events(trip_id)
        except Exception as e:
            logger.error(f"Failed to get events for trip {trip_id}: {e}")
            events = []

        details = format_trip_card(trip)

        if events:
            details += "\n\n📋 **История событий:**\n"
            for event in events[-5:]:  # Последние 5 событий
                try:
                    dt = isoparse(event['created_at'])
                    date_str = dt.strftime('%d.%m %H:%M')
                except:
                    date_str = event['created_at']

                details += f"• {date_str}: {event['description']}\n"

        await callback.message.answer(details, parse_mode="Markdown")
        await callback.answer()

    else:
        await callback.answer("❌ Неизвестное действие")


@router.message(Command("trip"))
async def show_trip_by_number(message: Message):
    """
    Показать рейс по номеру.

    Использование: /trip ТЛ-142
    """
    # Извлекаем номер рейса из команды
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Укажите номер рейса:\n"
            "/trip ТЛ-142"
        )
        return

    trip_number = parts[1].strip()

    try:
        trip = await db_trips.get_trip_by_number(trip_number)
    except Exception as e:
        logger.error(f"Failed to get trip {trip_number}: {e}")
        await message.answer("❌ Ошибка при получении рейса")
        return

    if not trip:
        await message.answer(f"❌ Рейс #{trip_number} не найден")
        return

    # Проверяем, что это рейс пользователя
    if trip['user_id'] != message.from_user.id:
        await message.answer("❌ Этот рейс назначен другому водителю")
        return

    card = format_trip_card(trip)
    await message.answer(
        card,
        reply_markup=trip_management_kb(trip['trip_id']),
        parse_mode="Markdown"
    )
