"""
Обработчики рейсов для водителей.
"""

import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

import db_trips

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data.startswith("activate_my_trip:"))
async def activate_my_trip(callback: CallbackQuery):
    """Активация рейса водителем."""
    trip_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    try:
        trip = await db_trips.get_trip(trip_id)
        if not trip:
            await callback.answer("❌ Рейс не найден", show_alert=True)
            return

        # Проверяем, что это рейс этого водителя
        if trip['user_id'] != user_id:
            await callback.answer("❌ Это не ваш рейс", show_alert=True)
            return

        # Проверяем статус
        if trip['status'] != 'assigned':
            await callback.answer(
                f"Рейс уже активирован (статус: {trip['status']})",
                show_alert=True
            )
            return

        # Активируем
        await db_trips.activate_trip(trip_id, user_id)

        await callback.message.edit_text(
            f"✅ **Рейс #{trip['trip_number']} активирован!**\n\n"
            f"Не забывайте:\n"
            f"📍 Делиться местоположением каждые 12 часов\n"
            f"📸 Отправить фото погрузки\n"
            f"📄 Отправить акты приема-передачи\n"
            f"📄 Отправить товарные накладные",
            parse_mode="Markdown"
        )

        await callback.answer("✅ Рейс активирован!")

        # Отправляем главное меню
        from bot.keyboards import location_kb
        await callback.message.answer(
            "Используйте кнопки ниже:",
            reply_markup=location_kb()
        )

    except Exception as e:
        logger.error(f"Failed to activate trip: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("view_my_trip:"))
@router.message(Command("my_trip"))
@router.message(F.text == "📋 Мой рейс")
async def view_my_trip(event):
    """Просмотр активного рейса водителем."""

    # Определяем тип события
    if isinstance(event, CallbackQuery):
        callback = event
        user_id = callback.from_user.id

        if callback.data.startswith("view_my_trip:"):
            trip_id = int(callback.data.split(":")[1])
            trip = await db_trips.get_trip(trip_id)
        else:
            trips = await db_trips.get_user_active_trips(user_id)
            trip = trips[0] if trips else None
    else:
        message = event
        user_id = message.from_user.id
        trips = await db_trips.get_user_active_trips(user_id)
        trip = trips[0] if trips else None

    if not trip:
        text = "У вас нет активных рейсов.\n\nОжидайте назначения от куратора."

        if isinstance(event, CallbackQuery):
            await event.message.edit_text(text)
            await event.answer()
        else:
            await event.answer(text)
        return

    # Проверяем права
    if trip['user_id'] != user_id:
        if isinstance(event, CallbackQuery):
            await event.answer("❌ Это не ваш рейс", show_alert=True)
        return

    # Статус с прогресс-баром
    status_map = {
        'assigned': ('⏳ Ожидает активации', '⚪⚪⚪⚪⚪'),
        'active': ('🟢 Активен', '🟢⚪⚪⚪⚪'),
        'loading': ('📦 Погрузка', '🟢🟢⚪⚪⚪'),
        'in_transit': ('🚚 В пути', '🟢🟢🟢⚪⚪'),
        'unloading': ('📥 Выгрузка', '🟢🟢🟢🟢⚪'),
        'completed': ('✅ Завершен', '🟢🟢🟢🟢🟢')
    }
    status_text, progress = status_map.get(trip['status'], (trip['status'], ''))

    # Формируем кнопки
    kb = InlineKeyboardBuilder()

    if trip['status'] not in ['completed', 'cancelled']:
        kb.button(text="🚚 Изменить статус", callback_data=f"change_status:{trip['trip_id']}")

    kb.button(text="ℹ️ Детали", callback_data=f"trip_details:{trip['trip_id']}")
    kb.adjust(2)

    text = (
        f"🚚 **Рейс #{trip['trip_number']}**\n"
        f"{progress} {status_text}\n\n"
        f"📍 **Маршрут:**\n"
        f"   Погрузка: {trip['loading_address']}\n"
        f"   📅 {trip['loading_date']}\n\n"
        f"   Выгрузка: {trip['unloading_address']}\n"
        f"   📅 {trip['unloading_date']}\n\n"
        f"💰 Ставка: {trip['rate']:,.0f} ₽"
    )

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="Markdown")
        await event.answer()
    else:
        await event.answer(text, reply_markup=kb.as_markup(), parse_mode="Markdown")


@router.callback_query(F.data.startswith("change_status:"))
async def change_status_menu(callback: CallbackQuery):
    """Меню изменения статуса рейса."""
    trip_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    try:
        trip = await db_trips.get_trip(trip_id)
        if not trip or trip['user_id'] != user_id:
            await callback.answer("❌ Ошибка", show_alert=True)
            return

        # Формируем доступные статусы
        kb = InlineKeyboardBuilder()

        if trip['status'] == 'active':
            kb.button(text="📦 Начал погрузку", callback_data=f"set_status:{trip_id}:loading")

        if trip['status'] in ['active', 'loading']:
            kb.button(text="🚚 Погрузился, в пути", callback_data=f"set_status:{trip_id}:in_transit")

        if trip['status'] == 'in_transit':
            kb.button(text="📥 Начал выгрузку", callback_data=f"set_status:{trip_id}:unloading")

        if trip['status'] in ['active', 'loading', 'in_transit', 'unloading']:
            kb.button(text="✅ Завершить рейс", callback_data=f"set_status:{trip_id}:completed")

        kb.button(text="◀️ Отмена", callback_data=f"view_my_trip:{trip_id}")
        kb.adjust(1)

        status_names = {
            'active': 'Активен',
            'loading': 'Погрузка',
            'in_transit': 'В пути',
            'unloading': 'Выгрузка'
        }

        await callback.message.edit_text(
            f"🚚 **Изменение статуса**\n\n"
            f"Рейс #{trip['trip_number']}\n"
            f"Текущий статус: {status_names.get(trip['status'], trip['status'])}\n\n"
            f"Выберите новый статус:",
            reply_markup=kb.as_markup(),
            parse_mode="Markdown"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Failed to show status menu: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("set_status:"))
async def set_status(callback: CallbackQuery):
    """Установка нового статуса рейса."""
    parts = callback.data.split(":")
    trip_id = int(parts[1])
    new_status = parts[2]
    user_id = callback.from_user.id

    try:
        trip = await db_trips.get_trip(trip_id)
        if not trip or trip['user_id'] != user_id:
            await callback.answer("❌ Ошибка", show_alert=True)
            return

        # Если завершение - показываем подтверждение
        if new_status == 'completed':
            kb = InlineKeyboardBuilder()
            kb.button(text="✅ Да, завершить", callback_data=f"confirm_status:{trip_id}:completed")
            kb.button(text="❌ Отмена", callback_data=f"change_status:{trip_id}")
            kb.adjust(1, 1)

            await callback.message.edit_text(
                f"⚠️ **Завершение рейса #{trip['trip_number']}**\n\n"
                f"Завершить рейс?\n"
                f"(Отслеживание местоположения будет остановлено)",
                reply_markup=kb.as_markup(),
                parse_mode="Markdown"
            )
        else:
            # Обычное изменение статуса
            await db_trips.update_trip_status(trip_id, new_status, user_id)

            # Возвращаемся к карточке
            await view_my_trip(callback)
            await callback.answer("✅ Статус обновлен")

    except Exception as e:
        logger.error(f"Failed to set status: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("confirm_status:"))
async def confirm_status(callback: CallbackQuery):
    """Подтверждение изменения статуса."""
    parts = callback.data.split(":")
    trip_id = int(parts[1])
    new_status = parts[2]
    user_id = callback.from_user.id

    try:
        trip = await db_trips.get_trip(trip_id)
        if not trip or trip['user_id'] != user_id:
            await callback.answer("❌ Ошибка", show_alert=True)
            return

        # Обновляем статус
        await db_trips.update_trip_status(trip_id, new_status, user_id)

        # Если завершен - останавливаем отслеживание
        if new_status == 'completed':
            from db import set_active
            await set_active(user_id, False)

        await callback.message.edit_text(
            f"✅ **Рейс #{trip['trip_number']} завершен!**\n\n"
            f"Спасибо за работу! 🎉\n\n"
            f"Отслеживание местоположения остановлено.\n"
            f"При получении нового рейса вы получите уведомление.",
            parse_mode="Markdown"
        )

        await callback.answer("✅ Рейс завершен!")

        # Отправляем кнопки
        from bot.keyboards import location_kb
        await callback.message.answer(
            "Используйте кнопки ниже:",
            reply_markup=location_kb()
        )

    except Exception as e:
        logger.error(f"Failed to confirm status: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("trip_details:"))
async def trip_details(callback: CallbackQuery):
    """Детали рейса для водителя."""
    trip_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    try:
        trip = await db_trips.get_trip(trip_id)
        if not trip or trip['user_id'] != user_id:
            await callback.answer("❌ Ошибка", show_alert=True)
            return

        # Получаем события
        events = await db_trips.get_trip_events(trip_id, limit=5)

        text = f"ℹ️ **Детали рейса #{trip['trip_number']}**\n\n"
        text += f"📞 Телефон поддержки: (укажите номер)\n\n"
        text += f"**Адрес погрузки:**\n{trip['loading_address']}\n"
        text += f"📅 {trip['loading_date']}\n\n"
        text += f"**Адрес выгрузки:**\n{trip['unloading_address']}\n"
        text += f"📅 {trip['unloading_date']}\n\n"
        text += f"💰 Ставка: {trip['rate']:,.0f} ₽\n\n"

        if events:
            text += "**Последние события:**\n"
            for event in events:
                created_at = event['created_at'][:16].replace('T', ' ')
                text += f"• {created_at} - {event['description']}\n"

        # Кнопка назад
        kb = InlineKeyboardBuilder()
        kb.button(text="◀️ Назад", callback_data=f"view_my_trip:{trip_id}")

        await callback.message.edit_text(
            text,
            reply_markup=kb.as_markup(),
            parse_mode="Markdown"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Failed to show details: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
