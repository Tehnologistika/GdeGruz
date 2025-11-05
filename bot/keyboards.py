from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def main_kb() -> ReplyKeyboardMarkup:
    """
    Главная клавиатура бота (при старте).

    ИСПОЛЬЗУЕТСЯ ТОЛЬКО ПРИ ПЕРВОМ ЗАПУСКЕ
    для запроса номера телефона.
    """
    kb = ReplyKeyboardBuilder()
    kb.button(text="📱 Поделиться номером", request_contact=True)
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)


def location_kb() -> ReplyKeyboardMarkup:
    """
    Клавиатура после регистрации водителя.

    ОСНОВНАЯ КЛАВИАТУРА для повседневной работы.
    """
    kb = ReplyKeyboardBuilder()
    kb.button(text="📍 Поделиться местоположением", request_location=True)
    kb.button(text="📤 Отправить документы")
    kb.button(text="📋 Мой рейс")
    kb.button(text="❓ Помощь")
    kb.button(text="🛑 Закончить отслеживание")
    kb.adjust(1, 2, 1, 1)
    return kb.as_markup(resize_keyboard=True)


def curator_kb() -> ReplyKeyboardMarkup:
    """
    Клавиатура для куратора рейсов.

    Содержит кнопки управления рейсами вместо команд.
    """
    kb = ReplyKeyboardBuilder()
    kb.button(text="🎛 Панель управления")
    kb.button(text="➕ Создать рейс")
    kb.button(text="📋 Список рейсов")
    kb.button(text="📊 Статистика")
    kb.adjust(2, 2)
    return kb.as_markup(resize_keyboard=True)


def resume_kb() -> ReplyKeyboardMarkup:
    """Клавиатура для возобновления отслеживания."""
    kb = ReplyKeyboardBuilder()
    kb.button(text="Возобновить отслеживание")
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)
