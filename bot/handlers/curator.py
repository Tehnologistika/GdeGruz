"""
Обработчики для кураторов рейсов.

Доступны только пользователям с ID из CURATOR_IDS.
"""

import os
import logging
from typing import List
from datetime import datetime, timezone, timedelta

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
            "🎛 **Панель управления рейсами**\n\n"
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
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Failed to show admin panel: {e}", exc_info=True)
        await message.answer(
            "❌ Ошибка загрузки панели управления.\n"
            "Попробуйте позже."
        )


# ========== Обработчики кнопок куратора ==========


@router.message(F.text == "🎛 Панель управления")
async def panel_button(message: Message):
    """
    Обработчик кнопки 'Панель управления'.

    Вызывает admin_panel для показа панели управления.
    """
    if not is_curator(message.from_user.id):
        await message.answer("❌ Эта кнопка доступна только кураторам")
        return

    await admin_panel(message)


@router.message(F.text == "➕ Создать рейс")
async def create_trip_button(message: Message, state: FSMContext):
    """
    Обработчик кнопки 'Создать рейс'.

    Вызывает start_create_trip для начала создания рейса.
    """
    if not is_curator(message.from_user.id):
        await message.answer("❌ Эта кнопка доступна только кураторам")
        return

    await start_create_trip(message, state)


@router.message(F.text == "📋 Список рейсов")
async def trips_list_button(message: Message):
    """
    Обработчик кнопки 'Список рейсов'.

    Вызывает list_trips_command для показа списка рейсов.
    """
    if not is_curator(message.from_user.id):
        await message.answer("❌ Эта кнопка доступна только кураторам")
        return

    await list_trips_command(message)


@router.message(F.text == "📊 Статистика")
async def statistics_button(message: Message):
    """
    Обработчик кнопки 'Статистика'.

    Показывает панель управления со статистикой.
    """
    if not is_curator(message.from_user.id):
        await message.answer("❌ Эта кнопка доступна только кураторам")
        return

    await admin_panel(message)


# ========== Обработчики команд ==========


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
                "📋 **Активные рейсы**\n\n"
                "Нет активных рейсов.\n\n"
                "Используйте /create_trip для создания нового рейса.",
                reply_markup=kb.as_markup(),
                parse_mode="Markdown"
            )
            return

        # Формируем список
        text = "📋 **Активные рейсы:**\n\n"

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
                f"{emoji} **{trip['trip_number']}** - {trip['phone']}\n"
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
            parse_mode="Markdown"
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
        "➕ **Создание рейса**\n\n"
        "Отправьте данные одним сообщением:\n\n"
        "```\n"
        "Телефон водителя\n"
        "Адрес погрузки\n"
        "Дата погрузки (ДД.ММ)\n"
        "Адрес выгрузки\n"
        "Дата выгрузки (ДД.ММ)\n"
        "Ставка\n"
        "```\n\n"
        "**Пример:**\n"
        "```\n"
        "+79991234567\n"
        "Москва, ул. Ленина 1\n"
        "20.11\n"
        "Питер, Невский 100\n"
        "21.11\n"
        "50000\n"
        "```",
        parse_mode="Markdown",
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
            "2. Адрес погрузки\n"
            "3. Дата погрузки\n"
            "4. Адрес выгрузки\n"
            "5. Дата выгрузки\n"
            "6. Ставка\n\n"
            "Попробуйте еще раз или /cancel"
        )
        return

    phone = lines[0]
    loading_address = lines[1]
    loading_date = lines[2]
    unloading_address = lines[3]
    unloading_date = lines[4]
    rate = lines[5]

    # Валидация телефона (международный формат)
    import phonenumbers
    try:
        parsed_phone = phonenumbers.parse(phone, None)
        if not phonenumbers.is_valid_number(parsed_phone):
            raise ValueError("Invalid phone number")
        # Нормализуем формат
        phone = phonenumbers.format_number(parsed_phone, phonenumbers.PhoneNumberFormat.E164)
    except Exception:
        await message.answer(
            "❌ Неверный формат телефона!\n"
            "Примеры: +79991234567, +380501234567\n\n"
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
        kb.adjust(2, 1, 1)

        # Определяем статус
        if user_id:
            status_text = "⏳ Ожидает активации водителем"
            warning = ""
        else:
            status_text = "⚠️ Водитель не зарегистрирован в боте"
            warning = "\n\n⚠️ Водитель должен запустить бота и поделиться номером."

        # Отправляем куратору
        await message.answer(
            f"✅ **Рейс создан!**\n\n"
            f"🚚 Рейс **#{trip_number}**\n"
            f"📞 Водитель: {phone}\n"
            f"📍 {loading_address}\n"
            f"     ↓\n"
            f"📍 {unloading_address}\n"
            f"📅 {loading_date} → {unloading_date}\n"
            f"💰 {rate_float:,.0f} ₽\n\n"
            f"Статус: {status_text}"
            f"{warning}",
            reply_markup=kb.as_markup(),
            parse_mode="Markdown"
        )

        # Уведомляем в группу кураторов
        if GROUP_CHAT_ID:
            try:
                await message.bot.send_message(
                    GROUP_CHAT_ID,
                    f"🆕 **Создан новый рейс**\n\n"
                    f"🚚 Рейс #{trip_number}\n"
                    f"📞 {phone}\n"
                    f"📍 {loading_address} → {unloading_address}\n"
                    f"📅 {loading_date} → {unloading_date}\n"
                    f"💰 {rate_float:,.0f} ₽\n\n"
                    f"Куратор: {message.from_user.full_name}",
                    parse_mode="Markdown"
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
            f"✅ **Рейс активирован!**\n\n"
            f"🚚 Рейс #{trip['trip_number']}\n"
            f"📞 {trip['phone']}\n"
            f"📍 {trip['loading_address']} → {trip['unloading_address']}\n"
            f"📅 {trip['loading_date']} → {trip['unloading_date']}\n"
            f"💰 {trip['rate']:,.0f} ₽\n\n"
            f"Статус: 🟢 Активен\n"
            f"Уведомление отправлено водителю.",
            reply_markup=kb.as_markup(),
            parse_mode="Markdown"
        )

        # Отправляем уведомление водителю
        if trip['user_id'] and trip['user_id'] > 0:
            try:
                await callback.bot.send_message(
                    trip['user_id'],
                    f"🚚 **Ваш рейс активирован куратором!**\n\n"
                    f"Рейс #{trip['trip_number']}\n"
                    f"📍 {trip['loading_address']}\n"
                    f"     ↓\n"
                    f"📍 {trip['unloading_address']}\n"
                    f"📅 Погрузка: {trip['loading_date']}\n"
                    f"📅 Выгрузка: {trip['unloading_date']}\n"
                    f"💰 Ставка: {trip['rate']:,.0f} ₽\n\n"
                    f"Не забывайте делиться местоположением!",
                    parse_mode="Markdown"
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
            from datetime import datetime, timezone
            ts = last_loc['ts']
            # ts уже datetime объект с timezone из db.get_last_point
            if isinstance(ts, str):
                last_time = datetime.fromisoformat(ts)
            else:
                last_time = ts
            # Убеждаемся что last_time aware
            if last_time.tzinfo is None:
                last_time = last_time.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delta = now - last_time

            if delta.total_seconds() < 3600:
                loc_text = f"{int(delta.total_seconds() / 60)} мин назад"
            elif delta.total_seconds() < 86400:
                loc_text = f"{int(delta.total_seconds() / 3600)} ч назад"
            else:
                loc_text = f"{int(delta.total_seconds() / 86400)} дн назад"
        else:
            loc_text = "нет данных"

        # Визуализация прогресса рейса
        progress_stages = {
            'assigned': ('⏳', '⬜️', '⬜️', '⬜️', '⬜️'),
            'active': ('✅', '🟢', '⬜️', '⬜️', '⬜️'),
            'in_transit': ('✅', '✅', '🚚', '⬜️', '⬜️'),
            'delivered': ('✅', '✅', '✅', '📦', '⬜️'),
            'completed': ('✅', '✅', '✅', '✅', '✅'),
            'cancelled': ('❌', '❌', '❌', '❌', '❌')
        }

        progress = progress_stages.get(trip['status'], ('⬜️', '⬜️', '⬜️', '⬜️', '⬜️'))
        progress_bar = ' → '.join(progress)

        status_descriptions = {
            'assigned': '⏳ **Ожидает активации**\nВодитель ещё не поделился номером',
            'active': '🟢 **Активен**\nВодитель готовится к погрузке',
            'in_transit': '🚚 **В пути**\nГруз погружен, едет на выгрузку',
            'delivered': '📦 **Доставлен**\nГруз выгружен, ожидаем оригиналы документов',
            'completed': '✅ **Завершён**\nВсе документы получены, рейс закрыт',
            'cancelled': '❌ **Отменён**'
        }
        status_text = status_descriptions.get(trip['status'], trip['status'])

        # Получаем информацию о документах
        import db_documents
        docs_check = await db_documents.get_trip_documents_summary(trip_id)

        # Формируем текст о документах
        docs_text = "\n\n📄 **Документы:**\n"

        # Документы погрузки
        loading = docs_check['loading']
        docs_text += f"{'✅' if loading['has_loading_photo'] else '❌'} Фото погрузки: {loading['loading_photo_count']}\n"
        docs_text += f"{'✅' if loading['has_acceptance_act'] else '❌'} Акт приёма: {loading['acceptance_act_count']}\n"

        # Документы выгрузки
        unloading = docs_check['unloading']
        docs_text += f"{'✅' if unloading['has_unloading_photo'] else '❌'} Фото выгрузки: {unloading['unloading_photo_count']}\n"
        docs_text += f"{'✅' if unloading['has_invoice'] else '❌'} Накладные: {unloading['invoice_count']}"

        # Формируем кнопки в зависимости от статуса
        kb = InlineKeyboardBuilder()

        # Кнопки действий в зависимости от статуса
        if trip['status'] == 'assigned':
            kb.button(text="🚀 Активировать", callback_data=f"activate_trip:{trip_id}")
        elif trip['status'] == 'active':
            kb.button(text="📦 Груз доставлен", callback_data=f"mark_delivered:{trip_id}")
        elif trip['status'] == 'in_transit':
            kb.button(text="📦 Груз доставлен", callback_data=f"mark_delivered:{trip_id}")
        elif trip['status'] == 'delivered':
            kb.button(text="✅ Завершить (с СДЭК)", callback_data=f"complete_trip:{trip_id}")

        # Общие кнопки
        kb.button(text="📍 Местоположение", callback_data=f"request_location:{trip_id}")
        kb.button(text="📋 История", callback_data=f"trip_history:{trip_id}")

        # Кнопка отмены (для незавершенных рейсов)
        if trip['status'] not in ['completed', 'cancelled']:
            kb.button(text="❌ Отменить", callback_data=f"cancel_trip:{trip_id}")

        kb.button(text="◀️ Назад", callback_data="list_trips")
        kb.adjust(1, 2, 1, 1)

        await callback.message.edit_text(
            f"🚚 **Рейс #{trip['trip_number']}**\n\n"
            f"{status_text}\n\n"
            f"**Прогресс:**\n{progress_bar}\n"
            f"Назначен → Активен → В пути → Доставлен → Завершён\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📞 Водитель: {trip['phone']}\n"
            f"📍 Откуда: {trip['loading_address']}\n"
            f"📅 {trip['loading_date']}\n\n"
            f"📍 Куда: {trip['unloading_address']}\n"
            f"📅 {trip['unloading_date']}\n\n"
            f"💰 Ставка: {trip['rate']:,.0f} ₽\n"
            f"{docs_text}\n\n"
            f"📍 Последняя локация: {loc_text}\n"
            f"🕐 Создан: {trip['created_at'][:10]}",
            reply_markup=kb.as_markup(),
            parse_mode="Markdown"
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
            f"📍 **Запрос местоположения**\n\n"
            f"Отправить водителю напоминание\n"
            f"о необходимости поделиться\n"
            f"местоположением?\n\n"
            f"📞 {trip['phone']}\n"
            f"🚚 Рейс #{trip['trip_number']}",
            reply_markup=kb.as_markup(),
            parse_mode="Markdown"
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
            f"📍 **Напоминание от куратора**\n\n"
            f"Пожалуйста, поделитесь текущим местоположением.\n\n"
            f"🚚 Рейс #{trip['trip_number']}",
            reply_markup=kb.as_markup(resize_keyboard=True),
            parse_mode="Markdown"
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
            f"⚠️ **Завершение рейса #{trip['trip_number']}**\n\n"
            f"📞 Водитель: {trip['phone']}\n"
            f"📍 {trip['loading_address']} → {trip['unloading_address']}\n\n"
            f"Завершить рейс?",
            reply_markup=kb.as_markup(),
            parse_mode="Markdown"
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
            f"✅ **Рейс #{trip['trip_number']} завершен!**\n\n"
            f"Уведомление отправлено водителю.\n"
            f"Отслеживание остановлено.",
            parse_mode="Markdown"
        )

        # Уведомляем водителя
        if trip['user_id'] and trip['user_id'] > 0:
            try:
                await callback.bot.send_message(
                    trip['user_id'],
                    f"✅ **Рейс #{trip['trip_number']} завершен!**\n\n"
                    f"Спасибо за работу! 🎉\n\n"
                    f"Отслеживание местоположения остановлено.\n"
                    f"При получении нового рейса вы получите уведомление.",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.warning(f"Failed to notify driver: {e}")

        # Уведомляем группу о завершении рейса
        if GROUP_CHAT_ID:
            try:
                # Формируем полную карточку рейса
                moscow_tz = timezone(timedelta(hours=3))
                completed_time = datetime.now(moscow_tz).strftime('%d.%m.%Y %H:%M')

                # Получаем имя куратора
                curator_name = callback.from_user.full_name if callback.from_user else "Неизвестно"

                notification_text = (
                    f"✅ **РЕЙС ЗАВЕРШЕН**\n\n"
                    f"🚚 **Рейс #{trip['trip_number']}**\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📞 **Водитель:** {trip['phone']}\n"
                    f"🆔 **User ID:** {trip['user_id'] if trip['user_id'] else 'Не зарегистрирован'}\n\n"
                    f"📍 **Маршрут:**\n"
                    f"   🔵 Погрузка: {trip['loading_address']}\n"
                    f"   📅 {trip['loading_date']}\n\n"
                    f"   🔴 Выгрузка: {trip['unloading_address']}\n"
                    f"   📅 {trip['unloading_date']}\n\n"
                    f"💰 **Ставка:** {trip['rate']:,.0f} ₽\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 **Завершил:** {curator_name}\n"
                    f"🕐 **Время завершения:** {completed_time}\n"
                    f"📊 **Создан:** {trip['created_at'][:10]}\n\n"
                    f"✅ Рейс успешно завершен! Отслеживание остановлено."
                )

                await callback.bot.send_message(
                    GROUP_CHAT_ID,
                    notification_text,
                    parse_mode="Markdown"
                )
                logger.info(f"Sent completion notification to group {GROUP_CHAT_ID} for trip #{trip['trip_number']}")
            except Exception as e:
                logger.error(f"Failed to send completion notification to group {GROUP_CHAT_ID}: {e}", exc_info=True)

        await callback.answer("✅ Рейс завершен!")

    except Exception as e:
        logger.error(f"Failed to complete trip: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("mark_delivered:"))
async def mark_delivered_callback(callback: CallbackQuery):
    """Отметить груз доставленным."""
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    trip_id = int(callback.data.split(":")[1])

    try:
        trip = await db_trips.get_trip(trip_id)
        if not trip:
            await callback.answer("❌ Рейс не найден", show_alert=True)
            return

        # Проверяем текущий статус
        if trip['status'] not in ['in_transit', 'active']:
            await callback.answer(
                f"❌ Рейс должен быть в статусе 'В пути' или 'Активен'",
                show_alert=True
            )
            return

        # ПРОВЕРЯЕМ документы выгрузки
        import db_documents
        check = await db_documents.check_unloading_documents(trip_id)

        if not check['has_unloading_photo'] or not check['has_invoice']:
            # Показываем предупреждение
            kb = InlineKeyboardBuilder()
            kb.button(text="⚠️ Да, отметить", callback_data=f"force_delivered:{trip_id}")
            kb.button(text="❌ Отмена", callback_data=f"view_trip:{trip_id}")
            kb.adjust(1, 1)

            await callback.message.edit_text(
                f"⚠️ **Внимание!**\n\n"
                f"**Документы выгрузки:**\n"
                f"{'✅' if check['has_unloading_photo'] else '❌'} Фото выгрузки: {check['unloading_photo_count']} шт\n"
                f"{'✅' if check['has_invoice'] else '❌'} Накладные: {check['invoice_count']} шт\n\n"
                f"Не все документы загружены.\n"
                f"Всё равно отметить доставленным?",
                reply_markup=kb.as_markup(),
                parse_mode="Markdown"
            )
            await callback.answer()
            return

        # Документы OK - переводим
        await confirm_delivered(callback, trip_id)

    except Exception as e:
        logger.error(f"Failed to mark delivered: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("force_delivered:"))
async def force_delivered_callback(callback: CallbackQuery):
    """Принудительно отметить доставленным (без всех документов)."""
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    trip_id = int(callback.data.split(":")[1])
    await confirm_delivered(callback, trip_id)


async def confirm_delivered(callback: CallbackQuery, trip_id: int):
    """Подтверждение отметки доставленным."""
    try:
        trip = await db_trips.get_trip(trip_id)
        if not trip:
            await callback.answer("❌ Рейс не найден", show_alert=True)
            return

        # Обновляем статус на 'delivered'
        await db_trips.update_trip_status(
            trip_id,
            'delivered',
            callback.from_user.id,
            comment="Груз доставлен, ожидаем оригиналы документов"
        )

        # Уведомляем куратора
        await callback.message.edit_text(
            f"✅ **Рейс #{trip['trip_number']} отмечен доставленным!**\n\n"
            f"Груз выгружен.\n"
            f"Ожидаем отправку оригиналов документов через СДЭК.",
            parse_mode="Markdown"
        )

        # Уведомляем водителя
        if trip['user_id'] and trip['user_id'] > 0:
            try:
                await callback.bot.send_message(
                    trip['user_id'],
                    f"📦 **Рейс #{trip['trip_number']}**\n\n"
                    f"✅ Груз доставлен!\n\n"
                    f"Пожалуйста, отправьте оригиналы документов через СДЭК.\n"
                    f"После отправки сообщите куратору трек-номер.",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.warning(f"Failed to notify driver: {e}")

        # Уведомляем группу
        if GROUP_CHAT_ID:
            try:
                await callback.bot.send_message(
                    GROUP_CHAT_ID,
                    f"📦 **ГРУЗ ДОСТАВЛЕН**\n\n"
                    f"🚚 Рейс #{trip['trip_number']}\n"
                    f"📞 {trip['phone']}\n\n"
                    f"Груз выгружен. Ожидаем оригиналы.",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.warning(f"Failed to notify group: {e}")

        await callback.answer("✅ Отмечено доставленным!")

    except Exception as e:
        logger.error(f"Failed to confirm delivery: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("cancel_trip:"))
async def cancel_trip_callback(callback: CallbackQuery):
    """Отмена рейса куратором."""
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
        kb.button(text="⚠️ Да, отменить", callback_data=f"confirm_cancel:{trip_id}")
        kb.button(text="❌ Назад", callback_data=f"view_trip:{trip_id}")
        kb.adjust(1, 1)

        await callback.message.edit_text(
            f"⚠️ **Отмена рейса #{trip['trip_number']}**\n\n"
            f"📞 Водитель: {trip['phone']}\n"
            f"📍 {trip['loading_address']} → {trip['unloading_address']}\n\n"
            f"Вы уверены, что хотите отменить рейс?",
            reply_markup=kb.as_markup(),
            parse_mode="Markdown"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Failed to prepare cancellation: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("confirm_cancel:"))
async def confirm_cancel_callback(callback: CallbackQuery):
    """Подтверждение отмены рейса."""
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    trip_id = int(callback.data.split(":")[1])

    try:
        trip = await db_trips.get_trip(trip_id)
        if not trip:
            await callback.answer("❌ Рейс не найден", show_alert=True)
            return

        # Отменяем рейс
        await db_trips.update_trip_status(
            trip_id,
            'cancelled',
            callback.from_user.id,
            comment="Рейс отменён куратором"
        )

        # Уведомляем куратора
        await callback.message.edit_text(
            f"❌ **Рейс #{trip['trip_number']} отменён**\n\n"
            f"Рейс успешно отменён.",
            parse_mode="Markdown"
        )

        # Уведомляем водителя
        if trip['user_id'] and trip['user_id'] > 0:
            try:
                await callback.bot.send_message(
                    trip['user_id'],
                    f"❌ **Рейс #{trip['trip_number']} отменён**\n\n"
                    f"К сожалению, рейс был отменён.\n"
                    f"За подробностями обратитесь к куратору.",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.warning(f"Failed to notify driver: {e}")

        # Уведомляем группу
        if GROUP_CHAT_ID:
            try:
                await callback.bot.send_message(
                    GROUP_CHAT_ID,
                    f"❌ **РЕЙС ОТМЕНЁН**\n\n"
                    f"🚚 Рейс #{trip['trip_number']}\n"
                    f"📞 {trip['phone']}\n"
                    f"👤 Отменил: {callback.from_user.full_name}",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.warning(f"Failed to notify group: {e}")

        await callback.answer("❌ Рейс отменён")

    except Exception as e:
        logger.error(f"Failed to cancel trip: {e}", exc_info=True)
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
                "📋 **Все рейсы**\n\n"
                "Нет рейсов.\n\n"
                "Используйте /create_trip для создания нового рейса.",
                reply_markup=kb.as_markup(),
                parse_mode="Markdown"
            )
            await callback.answer()
            return

        # Формируем список
        text = "📊 **Все рейсы** (последние 10):\n\n"

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
                f"{emoji} **{trip['trip_number']}** - {trip['phone']}\n"
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
            parse_mode="Markdown"
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
                "📋 **Активные рейсы**\n\n"
                "Нет активных рейсов.\n\n"
                "Используйте /create_trip для создания нового рейса.",
                reply_markup=kb.as_markup(),
                parse_mode="Markdown"
            )
            await callback.answer()
            return

        # Формируем список
        text = "📋 **Активные рейсы:**\n\n"

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
                f"{emoji} **{trip['trip_number']}** - {trip['phone']}\n"
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
            parse_mode="Markdown"
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
                "✅ **Завершенные рейсы**\n\n"
                "Нет завершенных рейсов.",
                reply_markup=kb.as_markup(),
                parse_mode="Markdown"
            )
            await callback.answer()
            return

        # Формируем список
        text = "✅ **Завершенные рейсы** (последние 10):\n\n"

        for trip in completed_trips[:10]:
            completed_date = trip.get('completed_at', '')[:10] if trip.get('completed_at') else 'н/д'
            text += (
                f"✅ **{trip['trip_number']}** - {trip['phone']}\n"
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
            parse_mode="Markdown"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Failed to list completed trips: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(F.data == "back_to_admin")
async def back_to_admin_callback(callback: CallbackQuery):
    """Вернуться к админ-панели."""
    # ВАЖНО: используем callback.from_user.id, а не message.from_user.id
    # потому что callback.message - это сообщение БОТА, а не пользователя
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    try:
        # Получаем статистику
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

        # Используем edit_text вместо answer, т.к. это inline callback
        await callback.message.edit_text(
            "🎛 **Панель управления рейсами**\n\n"
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
            parse_mode="Markdown"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Failed to show admin panel from callback: {e}", exc_info=True)
        await callback.answer("❌ Ошибка загрузки панели управления", show_alert=True)


@router.callback_query(F.data == "new_trip")
async def new_trip_callback(callback: CallbackQuery):
    """Создать новый рейс через callback."""
    await callback.message.answer(
        "Для создания нового рейса используйте команду /create_trip"
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

        text = f"📋 **История рейса #{trip['trip_number']}**\n\n"

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
            parse_mode="Markdown"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Failed to show history: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
