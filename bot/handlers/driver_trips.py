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

        # Проверяем, что это рейс этого водителя (по телефону)
        from db import get_phone
        driver_phone = await get_phone(user_id)
        if not driver_phone or trip['phone'] != driver_phone:
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
            # Получаем телефон водителя и ищем рейсы по телефону
            from db import get_phone
            phone = await get_phone(user_id)
            if phone:
                all_trips = await db_trips.get_trips_by_phone(phone)
                # Фильтруем только активные (не завершенные и не отмененные)
                trips = [t for t in all_trips if t.get('status') not in ['completed', 'cancelled']]
            else:
                trips = []
            trip = trips[0] if trips else None
    else:
        message = event
        user_id = message.from_user.id
        # Получаем телефон водителя и ищем рейсы по телефону
        from db import get_phone
        phone = await get_phone(user_id)
        if phone:
            all_trips = await db_trips.get_trips_by_phone(phone)
            # Фильтруем только активные (не завершенные и не отмененные)
            trips = [t for t in all_trips if t.get('status') not in ['completed', 'cancelled']]
        else:
            trips = []
        trip = trips[0] if trips else None

    if not trip:
        text = "У вас нет активных рейсов.\n\nОжидайте назначения от куратора."

        if isinstance(event, CallbackQuery):
            await event.message.edit_text(text)
            await event.answer()
        else:
            await event.answer(text)
        return

    # Проверяем права (по телефону)
    from db import get_phone
    driver_phone = await get_phone(user_id)
    if not driver_phone or trip['phone'] != driver_phone:
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
        if not trip:
            await callback.answer("❌ Рейс не найден", show_alert=True)
            return

        # Проверяем права (по телефону)
        from db import get_phone
        driver_phone = await get_phone(user_id)
        if not driver_phone or trip['phone'] != driver_phone:
            await callback.answer("❌ Это не ваш рейс", show_alert=True)
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
        if not trip:
            await callback.answer("❌ Рейс не найден", show_alert=True)
            return

        # Проверяем права (по телефону)
        from db import get_phone
        driver_phone = await get_phone(user_id)
        if not driver_phone or trip['phone'] != driver_phone:
            await callback.answer("❌ Это не ваш рейс", show_alert=True)
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
        if not trip:
            await callback.answer("❌ Рейс не найден", show_alert=True)
            return

        # Проверяем права (по телефону)
        from db import get_phone
        driver_phone = await get_phone(user_id)
        if not driver_phone or trip['phone'] != driver_phone:
            await callback.answer("❌ Это не ваш рейс", show_alert=True)
            return

        # Обновляем статус
        await db_trips.update_trip_status(trip_id, new_status, user_id)

        # Если завершен - останавливаем отслеживание и отправляем уведомления
        if new_status == 'completed':
            from db import set_active, get_driver_by_user_id
            await set_active(user_id, False)

            # Отправляем уведомления в группы кураторов
            CURATOR_GROUP_ID = -1002606502231  # Группа "Куратор Рейса"
            DOCUMENTS_GROUP_ID = -5054329274   # Группа "ГдеГруз Документы"

            # Получаем информацию о водителе
            driver_info = await get_driver_by_user_id(user_id)
            driver_name = driver_info.get('name', 'Неизвестный') if driver_info else 'Неизвестный'

            # Формируем сообщение для групп
            from datetime import datetime
            completion_message = (
                f"✅ <b>Рейс завершен водителем</b>\n\n"
                f"🚚 Рейс: <b>#{trip['trip_number']}</b>\n"
                f"👤 Водитель: {driver_name}\n"
                f"📞 Телефон: {trip['phone']}\n\n"
                f"📍 Маршрут:\n"
                f"   {trip['loading_address']}\n"
                f"   ↓\n"
                f"   {trip['unloading_address']}\n\n"
                f"📅 Даты: {trip['loading_date']} → {trip['unloading_date']}\n"
                f"💰 Ставка: {trip['rate']:,.0f} ₽\n\n"
                f"🕐 Завершен: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )

            # Отправляем в обе группы
            try:
                await callback.bot.send_message(
                    CURATOR_GROUP_ID,
                    completion_message,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Failed to send completion message to curator group: {e}")

            try:
                await callback.bot.send_message(
                    DOCUMENTS_GROUP_ID,
                    completion_message,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Failed to send completion message to documents group: {e}")

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
        if not trip:
            await callback.answer("❌ Рейс не найден", show_alert=True)
            return

        # Проверяем права (по телефону)
        from db import get_phone
        driver_phone = await get_phone(user_id)
        if not driver_phone or trip['phone'] != driver_phone:
            await callback.answer("❌ Это не ваш рейс", show_alert=True)
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


# ============================================================================
# Обработчик кнопки "Отправить документы"
# ============================================================================

@router.message(F.text == "📤 Отправить документы")
async def request_documents(message: Message):
    """Обработчик кнопки 'Отправить документы'."""
    await message.answer(
        "📤 <b>Отправка документов</b>\n\n"
        "Отправьте документы в виде:\n"
        "• Фотографий\n"
        "• PDF файлов\n"
        "• Других файлов\n\n"
        "Вы можете отправить несколько документов подряд.\n"
        "Они будут автоматически переданы куратору.",
        parse_mode="HTML"
    )


@router.message(F.document | F.photo)
async def handle_document(message: Message):
    """Обработка полученных документов от водителя."""
    import os

    # Получаем GROUP_CHAT_ID для отправки кураторам
    GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0"))

    if not GROUP_CHAT_ID:
        await message.answer(
            "❌ Не настроен GROUP_CHAT_ID для отправки документов.\n"
            "Обратитесь к администратору."
        )
        return

    try:
        # Получаем информацию о водителе
        from db import get_driver_by_user_id
        driver_info = await get_driver_by_user_id(message.from_user.id)

        driver_name = driver_info.get('name', 'Неизвестный') if driver_info else 'Неизвестный'
        driver_phone = driver_info.get('phone', '') if driver_info else ''

        # Формируем caption для куратора
        caption = (
            f"📄 <b>Документ от водителя</b>\n\n"
            f"👤 {driver_name}\n"
            f"📞 {driver_phone}\n"
            f"🆔 User ID: {message.from_user.id}"
        )

        # Пересылаем документ/фото кураторам
        if message.document:
            await message.bot.send_document(
                GROUP_CHAT_ID,
                message.document.file_id,
                caption=caption,
                parse_mode="HTML"
            )
        elif message.photo:
            await message.bot.send_photo(
                GROUP_CHAT_ID,
                message.photo[-1].file_id,  # Берем самое большое фото
                caption=caption,
                parse_mode="HTML"
            )

        # Подтверждаем водителю
        await message.answer(
            "✅ Документ отправлен куратору!",
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Failed to forward document: {e}", exc_info=True)
        await message.answer(
            "❌ Ошибка при отправке документа. Попробуйте еще раз."
        )


# ============================================================================
# Обработчик кнопки "Завершить рейс"
# ============================================================================

@router.message(F.text == "✅ Завершить рейс")
async def complete_trip_button(message: Message):
    """Обработчик кнопки 'Завершить рейс'."""
    user_id = message.from_user.id

    try:
        # Получаем телефон водителя
        from db import get_phone
        phone = await get_phone(user_id)

        if not phone:
            await message.answer(
                "❌ Не удалось определить ваш номер телефона.\n"
                "Пожалуйста, зарегистрируйтесь снова.",
                parse_mode="HTML"
            )
            return

        # Ищем активный рейс
        trips = await db_trips.get_trips_by_phone(phone)
        active_trip = None
        for trip in trips:
            if trip.get('status') not in ['completed', 'cancelled']:
                active_trip = trip
                break

        if not active_trip:
            await message.answer(
                "ℹ️ У вас нет активных рейсов для завершения.",
                parse_mode="HTML"
            )
            return

        # Показываем подтверждение с полной карточкой рейса
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        kb = InlineKeyboardBuilder()
        kb.button(
            text="✅ Да, завершить",
            callback_data=f"driver_complete:{active_trip['trip_id']}"
        )
        kb.button(text="❌ Отмена", callback_data="cancel_complete")
        kb.adjust(1, 1)

        # Статусы для отображения
        status_emoji = {
            'active': '🟢',
            'loading': '📦',
            'in_transit': '🚚',
            'unloading': '📥'
        }
        status_text = {
            'active': 'Активен',
            'loading': 'Погрузка',
            'in_transit': 'В пути',
            'unloading': 'Выгрузка'
        }

        current_status = active_trip.get('status', 'active')
        emoji = status_emoji.get(current_status, '🚚')
        status = status_text.get(current_status, 'Активен')

        await message.answer(
            f"⚠️ <b>Подтверждение завершения рейса</b>\n\n"
            f"🚚 <b>Рейс #{active_trip['trip_number']}</b>\n"
            f"{emoji} Статус: {status}\n\n"
            f"📍 <b>Погрузка:</b>\n{active_trip['loading_address']}\n"
            f"📅 {active_trip['loading_date']}\n\n"
            f"📍 <b>Выгрузка:</b>\n{active_trip['unloading_address']}\n"
            f"📅 {active_trip['unloading_date']}\n\n"
            f"💰 <b>Ставка:</b> {active_trip['rate']:,.0f} ₽\n\n"
            f"❓ <b>Вы уверены, что хотите завершить этот рейс?</b>\n"
            f"<i>(Отслеживание местоположения будет остановлено)</i>",
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Failed to show complete confirmation: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.callback_query(F.data.startswith("driver_complete:"))
async def confirm_driver_complete(callback: CallbackQuery):
    """Подтверждение завершения рейса водителем."""
    trip_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    try:
        trip = await db_trips.get_trip(trip_id)
        if not trip:
            await callback.answer("❌ Рейс не найден", show_alert=True)
            return

        # Проверяем права (по телефону)
        from db import get_phone, set_active, get_driver_by_user_id
        driver_phone = await get_phone(user_id)
        if not driver_phone or trip['phone'] != driver_phone:
            await callback.answer("❌ Это не ваш рейс", show_alert=True)
            return

        # Завершаем рейс
        await db_trips.update_trip_status(trip_id, 'completed', user_id)

        # Останавливаем отслеживание
        await set_active(user_id, False)

        # Отправляем уведомления в группы
        CURATOR_GROUP_ID = -1002606502231  # Группа "Куратор Рейса"
        DOCUMENTS_GROUP_ID = -5054329274   # Группа "ГдеГруз Документы"

        # Получаем информацию о водителе
        driver_info = await get_driver_by_user_id(user_id)
        driver_name = driver_info.get('name', 'Неизвестный') if driver_info else 'Неизвестный'

        # Формируем сообщение для групп
        from datetime import datetime
        completion_message = (
            f"✅ <b>Рейс завершен водителем</b>\n\n"
            f"🚚 Рейс: <b>#{trip['trip_number']}</b>\n"
            f"👤 Водитель: {driver_name}\n"
            f"📞 Телефон: {trip['phone']}\n\n"
            f"📍 Маршрут:\n"
            f"   {trip['loading_address']}\n"
            f"   ↓\n"
            f"   {trip['unloading_address']}\n\n"
            f"📅 Даты: {trip['loading_date']} → {trip['unloading_date']}\n"
            f"💰 Ставка: {trip['rate']:,.0f} ₽\n\n"
            f"🕐 Завершен: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )

        # Отправляем в группу "Куратор Рейса"
        try:
            await callback.bot.send_message(
                CURATOR_GROUP_ID,
                completion_message,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to notify curator group: {e}")

        # Отправляем в группу "ГдеГруз Документы"
        try:
            await callback.bot.send_message(
                DOCUMENTS_GROUP_ID,
                completion_message,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to notify documents group: {e}")

        # Уведомляем водителя
        await callback.message.edit_text(
            f"✅ <b>Рейс #{trip['trip_number']} завершен!</b>\n\n"
            f"Спасибо за работу! 🎉\n\n"
            f"Отслеживание местоположения остановлено.\n"
            f"При получении нового рейса вы получите уведомление.",
            parse_mode="HTML"
        )

        await callback.answer("✅ Рейс завершен!")

        # Отправляем кнопки
        from bot.keyboards import location_kb
        await callback.message.answer(
            "Используйте кнопки ниже:",
            reply_markup=location_kb()
        )

    except Exception as e:
        logger.error(f"Failed to complete trip: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(F.data == "cancel_complete")
async def cancel_complete(callback: CallbackQuery):
    """Отмена завершения рейса."""
    await callback.message.edit_text(
        "❌ Завершение отменено.\n\n"
        "Рейс остается активным.",
        parse_mode="HTML"
    )
    await callback.answer()

