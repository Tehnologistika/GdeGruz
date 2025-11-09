"""
Админ-панель для кураторов рейсов.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
from dateutil.parser import isoparse
import logging

import db_trips
import db_documents
from db import get_phone
from bot.utils import is_curator  # Импортируем is_curator из utils

router = Router()
logger = logging.getLogger(__name__)


class CreateTripStates(StatesGroup):
    """Состояния FSM для создания рейса."""
    trip_number = State()
    user_id = State()
    customer = State()
    carrier = State()
    loading_address = State()
    loading_date = State()
    unloading_address = State()
    unloading_date = State()
    cargo_type = State()
    rate = State()


def admin_main_menu() -> InlineKeyboardMarkup:
    """Главное меню админ-панели."""
    kb = InlineKeyboardBuilder()

    kb.button(text="➕ Создать рейс", callback_data="admin:create_trip")
    kb.button(text="📋 Активные рейсы", callback_data="admin:list_trips")
    kb.button(text="🔍 Найти рейс", callback_data="admin:search_trip")
    kb.button(text="📊 Статистика", callback_data="admin:stats")

    kb.adjust(2, 2)
    return kb.as_markup()


def trip_actions_menu(trip_id: int) -> InlineKeyboardMarkup:
    """Меню действий с рейсом."""
    kb = InlineKeyboardBuilder()

    kb.button(text="ℹ️ Детали", callback_data=f"admin:trip_details:{trip_id}")
    kb.button(text="🔄 Изменить статус", callback_data=f"admin:trip_status:{trip_id}")
    kb.button(text="📄 Документы", callback_data=f"admin:trip_docs:{trip_id}")
    kb.button(text="📍 Местоположение", callback_data=f"admin:trip_location:{trip_id}")
    kb.button(text="🔙 Назад", callback_data="admin:list_trips")

    kb.adjust(2, 2, 1)
    return kb.as_markup()


def status_menu(trip_id: int, current_status: str) -> InlineKeyboardMarkup:
    """Меню выбора статуса рейса."""
    kb = InlineKeyboardBuilder()

    statuses = [
        ("📋 Создан", "created"),
        ("📦 Погрузка", "loading"),
        ("🚚 В пути", "in_transit"),
        ("📥 Выгрузка", "unloading"),
        ("✅ Завершён", "completed"),
        ("❌ Отменён", "cancelled")
    ]

    for text, status in statuses:
        if status != current_status:
            kb.button(text=text, callback_data=f"admin:set_status:{trip_id}:{status}")

    kb.button(text="🔙 Назад", callback_data=f"admin:trip_details:{trip_id}")

    kb.adjust(2)
    return kb.as_markup()


def format_trip_card(trip: dict, detailed: bool = False) -> str:
    """Форматирование карточки рейса."""
    # Статусы с эмодзи
    status_emoji = {
        'created': '📋',
        'loading': '📦',
        'in_transit': '🚚',
        'unloading': '📥',
        'completed': '✅',
        'cancelled': '❌'
    }

    status_names = {
        'created': 'Создан',
        'loading': 'Погрузка',
        'in_transit': 'В пути',
        'unloading': 'Выгрузка',
        'completed': 'Завершён',
        'cancelled': 'Отменён'
    }

    emoji = status_emoji.get(trip['status'], '📋')
    status_name = status_names.get(trip['status'], trip['status'])

    # Форматирование дат
    loading_date = "не указана"
    unloading_date = "не указана"

    if trip.get('loading_date'):
        try:
            dt = isoparse(trip['loading_date'])
            loading_date = dt.strftime('%d.%m.%Y %H:%M')
        except:
            loading_date = trip['loading_date']

    if trip.get('unloading_date'):
        try:
            dt = isoparse(trip['unloading_date'])
            unloading_date = dt.strftime('%d.%m.%Y %H:%M')
        except:
            unloading_date = trip['unloading_date']

    # Базовая карточка
    card = (
        f"{emoji} **Рейс #{trip['trip_number']}**\n"
        f"📊 Статус: {status_name}\n"
        f"👤 Водитель: {trip.get('phone', trip['user_id'])}\n"
        f"💰 Ставка: {trip.get('rate', 0):,.0f} ₽\n"
    )

    if detailed:
        card += (
            f"\n📍 **Маршрут:**\n"
            f"  Погрузка: {trip.get('loading_address', 'не указан')}\n"
            f"  📅 {loading_date}\n"
            f"  Выгрузка: {trip.get('unloading_address', 'не указан')}\n"
            f"  📅 {unloading_date}\n\n"
            f"📦 Груз: {trip.get('cargo_type', 'не указан')}\n"
            f"🏢 Заказчик: {trip.get('customer', 'не указан')}\n"
            f"🚛 Перевозчик: {trip.get('carrier', 'не указан')}\n"
        )

        # Временные метки
        if trip.get('loading_confirmed_at'):
            try:
                dt = isoparse(trip['loading_confirmed_at'])
                card += f"✅ Прибыл на погрузку: {dt.strftime('%d.%m %H:%M')}\n"
            except:
                pass

        if trip.get('unloading_confirmed_at'):
            try:
                dt = isoparse(trip['unloading_confirmed_at'])
                card += f"✅ Прибыл на выгрузку: {dt.strftime('%d.%m %H:%M')}\n"
            except:
                pass

    return card


@router.message(Command("admin"))
async def admin_panel(message: Message):
    """Вход в админ-панель."""
    if not is_curator(message.from_user.id):
        await message.answer("❌ У вас нет доступа к админ-панели")
        return

    await message.answer(
        "👨‍💼 **Панель куратора**\n\n"
        "Выберите действие:",
        reply_markup=admin_main_menu(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin:menu")
async def show_admin_menu(callback: CallbackQuery):
    """Показать главное меню."""
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    await callback.message.edit_text(
        "👨‍💼 **Панель куратора**\n\n"
        "Выберите действие:",
        reply_markup=admin_main_menu(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:create_trip")
async def start_create_trip(callback: CallbackQuery, state: FSMContext):
    """Начать создание рейса."""
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    await state.set_state(CreateTripStates.trip_number)
    await callback.message.edit_text(
        "➕ **Создание нового рейса**\n\n"
        "Шаг 1/10: Введите номер рейса (например: ТЛ-142):",
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(CreateTripStates.trip_number)
async def process_trip_number(message: Message, state: FSMContext):
    """Обработка номера рейса."""
    await state.update_data(trip_number=message.text.strip())
    await state.set_state(CreateTripStates.user_id)

    await message.answer(
        "Шаг 2/10: Введите Telegram ID водителя (например: 123456789):"
    )


@router.message(CreateTripStates.user_id)
async def process_user_id(message: Message, state: FSMContext):
    """Обработка ID водителя."""
    try:
        user_id = int(message.text.strip())
        # Проверяем, существует ли водитель
        phone = await get_phone(user_id)
        if not phone:
            await message.answer(
                f"⚠️ Водитель с ID {user_id} не найден в системе.\n"
                "Продолжить? (да/нет)"
            )

        await state.update_data(user_id=user_id)
        await state.set_state(CreateTripStates.customer)

        await message.answer(
            f"Шаг 3/10: Введите название заказчика:"
        )
    except ValueError:
        await message.answer("❌ Неверный формат. Введите число:")


@router.message(CreateTripStates.customer)
async def process_customer(message: Message, state: FSMContext):
    """Обработка заказчика."""
    await state.update_data(customer=message.text.strip())
    await state.set_state(CreateTripStates.carrier)

    await message.answer("Шаг 4/10: Введите название перевозчика:")


@router.message(CreateTripStates.carrier)
async def process_carrier(message: Message, state: FSMContext):
    """Обработка перевозчика."""
    await state.update_data(carrier=message.text.strip())
    await state.set_state(CreateTripStates.loading_address)

    await message.answer("Шаг 5/10: Введите адрес погрузки:")


@router.message(CreateTripStates.loading_address)
async def process_loading_address(message: Message, state: FSMContext):
    """Обработка адреса погрузки."""
    await state.update_data(loading_address=message.text.strip())
    await state.set_state(CreateTripStates.loading_date)

    await message.answer(
        "Шаг 6/10: Введите дату и время погрузки\n"
        "Формат: ДД.ММ.ГГГГ ЧЧ:ММ\n"
        "Например: 15.11.2024 09:00"
    )


@router.message(CreateTripStates.loading_date)
async def process_loading_date(message: Message, state: FSMContext):
    """Обработка даты погрузки."""
    try:
        # Парсим дату
        dt = datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
        await state.update_data(loading_date=dt.isoformat())
        await state.set_state(CreateTripStates.unloading_address)

        await message.answer("Шаг 7/10: Введите адрес выгрузки:")
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты.\n"
            "Используйте: ДД.ММ.ГГГГ ЧЧ:ММ (например: 15.11.2024 09:00)"
        )


@router.message(CreateTripStates.unloading_address)
async def process_unloading_address(message: Message, state: FSMContext):
    """Обработка адреса выгрузки."""
    await state.update_data(unloading_address=message.text.strip())
    await state.set_state(CreateTripStates.unloading_date)

    await message.answer(
        "Шаг 8/10: Введите дату и время выгрузки\n"
        "Формат: ДД.ММ.ГГГГ ЧЧ:ММ"
    )


@router.message(CreateTripStates.unloading_date)
async def process_unloading_date(message: Message, state: FSMContext):
    """Обработка даты выгрузки."""
    try:
        dt = datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
        await state.update_data(unloading_date=dt.isoformat())
        await state.set_state(CreateTripStates.cargo_type)

        await message.answer("Шаг 9/10: Введите тип груза:")
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты.\n"
            "Используйте: ДД.ММ.ГГГГ ЧЧ:ММ"
        )


@router.message(CreateTripStates.cargo_type)
async def process_cargo_type(message: Message, state: FSMContext):
    """Обработка типа груза."""
    await state.update_data(cargo_type=message.text.strip())
    await state.set_state(CreateTripStates.rate)

    await message.answer("Шаг 10/10: Введите ставку (в рублях, например: 65000):")


@router.message(CreateTripStates.rate)
async def process_rate(message: Message, state: FSMContext):
    """Обработка ставки и создание рейса."""
    try:
        rate = float(message.text.strip().replace(',', '').replace(' ', ''))
        await state.update_data(rate=rate)

        # Получаем все данные
        data = await state.get_data()

        # Создаем рейс
        trip_id = await db_trips.create_trip(
            trip_number=data['trip_number'],
            user_id=data['user_id'],
            customer=data['customer'],
            carrier=data['carrier'],
            loading_address=data['loading_address'],
            loading_date=data['loading_date'],
            unloading_address=data['unloading_address'],
            unloading_date=data['unloading_date'],
            cargo_type=data['cargo_type'],
            rate=data['rate'],
            curator_id=message.from_user.id
        )

        await state.clear()

        # Показываем созданный рейс
        trip = await db_trips.get_trip(trip_id)
        card = format_trip_card(trip, detailed=True)

        await message.answer(
            f"✅ **Рейс успешно создан!**\n\n{card}",
            reply_markup=trip_actions_menu(trip_id),
            parse_mode="Markdown"
        )

    except ValueError:
        await message.answer("❌ Неверный формат. Введите число:")


@router.callback_query(F.data == "admin:list_trips")
async def list_active_trips(callback: CallbackQuery):
    """Показать список активных рейсов."""
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        trips = await db_trips.get_all_active_trips()

        if not trips:
            await callback.message.edit_text(
                "📋 Нет активных рейсов",
                reply_markup=InlineKeyboardBuilder().button(
                    text="🔙 Меню", callback_data="admin:menu"
                ).as_markup()
            )
            await callback.answer()
            return

        # Показываем список с кнопками
        kb = InlineKeyboardBuilder()

        text = f"📋 **Активные рейсы:** ({len(trips)})\n\n"

        for trip in trips[:10]:  # Первые 10
            status_emoji = {
                'created': '📋', 'loading': '📦', 'in_transit': '🚚',
                'unloading': '📥', 'completed': '✅', 'cancelled': '❌'
            }
            emoji = status_emoji.get(trip['status'], '📋')

            text += f"{emoji} #{trip['trip_number']} - {trip.get('phone', trip['user_id'])}\n"
            kb.button(
                text=f"#{trip['trip_number']}",
                callback_data=f"admin:trip_details:{trip['trip_id']}"
            )

        if len(trips) > 10:
            text += f"\n... и ещё {len(trips) - 10} рейсов"

        kb.button(text="🔙 Меню", callback_data="admin:menu")
        kb.adjust(3, 3, 3, 1)

        await callback.message.edit_text(
            text,
            reply_markup=kb.as_markup(),
            parse_mode="Markdown"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Failed to list trips: {e}")
        await callback.answer("❌ Ошибка при получении списка", show_alert=True)


@router.callback_query(F.data.startswith("admin:trip_details:"))
async def show_trip_details(callback: CallbackQuery):
    """Показать детали рейса."""
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    trip_id = int(callback.data.split(":")[2])

    try:
        trip = await db_trips.get_trip(trip_id)
        if not trip:
            await callback.answer("❌ Рейс не найден", show_alert=True)
            return

        # Получаем последние события
        events = await db_trips.get_trip_events(trip_id)

        card = format_trip_card(trip, detailed=True)

        if events:
            card += "\n\n📋 **Последние события:**\n"
            for event in events[-3:]:  # Последние 3
                try:
                    dt = isoparse(event['created_at'])
                    date_str = dt.strftime('%d.%m %H:%M')
                except:
                    date_str = event['created_at']

                card += f"• {date_str}: {event['description']}\n"

        await callback.message.edit_text(
            card,
            reply_markup=trip_actions_menu(trip_id),
            parse_mode="Markdown"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Failed to show trip details: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("admin:trip_status:"))
async def show_status_menu(callback: CallbackQuery):
    """Показать меню изменения статуса."""
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    trip_id = int(callback.data.split(":")[2])

    try:
        trip = await db_trips.get_trip(trip_id)
        if not trip:
            await callback.answer("❌ Рейс не найден", show_alert=True)
            return

        await callback.message.edit_text(
            f"🔄 **Изменение статуса рейса #{trip['trip_number']}**\n\n"
            f"Текущий статус: {trip['status']}\n\n"
            "Выберите новый статус:",
            reply_markup=status_menu(trip_id, trip['status']),
            parse_mode="Markdown"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Failed to show status menu: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("admin:set_status:"))
async def update_trip_status(callback: CallbackQuery):
    """Обновить статус рейса."""
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    parts = callback.data.split(":")
    trip_id = int(parts[2])
    new_status = parts[3]

    try:
        await db_trips.update_trip_status(trip_id, new_status, callback.from_user.id)

        trip = await db_trips.get_trip(trip_id)
        card = format_trip_card(trip, detailed=True)

        await callback.message.edit_text(
            f"✅ Статус обновлён!\n\n{card}",
            reply_markup=trip_actions_menu(trip_id),
            parse_mode="Markdown"
        )
        await callback.answer("✅ Статус обновлён")

    except Exception as e:
        logger.error(f"Failed to update status: {e}")
        await callback.answer("❌ Ошибка при обновлении", show_alert=True)


@router.callback_query(F.data.startswith("admin:trip_docs:"))
async def show_trip_documents(callback: CallbackQuery):
    """Показать документы рейса."""
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    trip_id = int(callback.data.split(":")[2])

    try:
        trip = await db_trips.get_trip(trip_id)
        docs = await db_documents.get_trip_documents(trip_id)

        if not docs:
            await callback.answer("📄 Документов пока нет", show_alert=True)
            return

        text = f"📄 **Документы рейса #{trip['trip_number']}**\n\n"

        doc_types = {
            "loading_photo": "📸 Фото погрузки",
            "unloading_photo": "📸 Фото выгрузки",
            "ttn": "📄 ТТН",
            "upd": "📄 УПД",
            "other": "📄 Другой"
        }

        for doc in docs:
            doc_type = doc_types.get(doc['doc_type'], doc['doc_type'])
            try:
                dt = isoparse(doc['created_at'])
                date_str = dt.strftime('%d.%m %H:%M')
            except:
                date_str = doc['created_at']

            text += f"• {doc_type} - {date_str}\n"

        kb = InlineKeyboardBuilder()
        kb.button(text="🔙 Назад", callback_data=f"admin:trip_details:{trip_id}")

        await callback.message.edit_text(
            text,
            reply_markup=kb.as_markup(),
            parse_mode="Markdown"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Failed to show documents: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("admin:trip_location:"))
async def show_trip_location(callback: CallbackQuery):
    """Показать местоположение водителя."""
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    trip_id = int(callback.data.split(":")[2])

    try:
        trip = await db_trips.get_trip(trip_id)
        from db import get_last_point

        last_point = await get_last_point(trip['user_id'])

        if not last_point:
            await callback.answer("📍 Нет данных о местоположении", show_alert=True)
            return

        # Отправляем местоположение
        await callback.message.answer_location(
            latitude=last_point['lat'],
            longitude=last_point['lon']
        )

        try:
            dt = isoparse(last_point['ts'])
            time_str = dt.strftime('%d.%m.%Y %H:%M')
        except:
            time_str = str(last_point['ts'])

        await callback.answer(f"📍 Последнее обновление: {time_str}")

    except Exception as e:
        logger.error(f"Failed to show location: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data == "admin:stats")
async def show_statistics(callback: CallbackQuery):
    """Показать статистику."""
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        trips = await db_trips.get_all_active_trips()

        # Считаем по статусам
        stats = {}
        for trip in trips:
            status = trip['status']
            stats[status] = stats.get(status, 0) + 1

        status_names = {
            'created': '📋 Создан',
            'loading': '📦 Погрузка',
            'in_transit': '🚚 В пути',
            'unloading': '📥 Выгрузка',
            'completed': '✅ Завершён',
            'cancelled': '❌ Отменён'
        }

        text = "📊 **Статистика рейсов**\n\n"
        text += f"Всего активных: {len(trips)}\n\n"

        for status, count in stats.items():
            name = status_names.get(status, status)
            text += f"{name}: {count}\n"

        kb = InlineKeyboardBuilder()
        kb.button(text="🔙 Меню", callback_data="admin:menu")

        await callback.message.edit_text(
            text,
            reply_markup=kb.as_markup(),
            parse_mode="Markdown"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Failed to show stats: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data == "admin:search_trip")
async def search_trip_prompt(callback: CallbackQuery, state: FSMContext):
    """Запросить номер рейса для поиска."""
    if not is_curator(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    await callback.message.edit_text(
        "🔍 Введите номер рейса для поиска:"
    )
    await callback.answer()
