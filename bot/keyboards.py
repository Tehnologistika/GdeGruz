from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def main_kb() -> ReplyKeyboardMarkup:
    """Главная клавиатура бота.

    Содержит две кнопки:
    1) «Поделиться номером»          – запрашивает контакт (телефон)
    2) «Поделиться местоположением»  – запрашивает координаты
    """
    kb = ReplyKeyboardBuilder()

    # Кнопка запроса телефона
    kb.button(text="Поделиться номером", request_contact=True)
    # Кнопка запроса локации
    kb.button(text="Поделиться местоположением", request_location=True)
    # Кнопка запроса помощи
    kb.button(text="Помощь")

    kb.adjust(1, 1, 1)  # каждая кнопка в своей строке
    return kb.as_markup(resize_keyboard=True)


def location_kb() -> ReplyKeyboardMarkup:
    """Клавиатура только с кнопкой запроса локации.

    Используется после того, как водитель уже поделился номером телефона.
    """
    kb = ReplyKeyboardBuilder()
    kb.button(text="Поделиться местоположением", request_location=True)
    kb.button(text="Помощь")
    kb.adjust(1, 1)
    return kb.as_markup(resize_keyboard=True)
