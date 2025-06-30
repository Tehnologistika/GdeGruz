
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

    kb.adjust(1)  # по одной кнопке в строке
    return kb.as_markup(resize_keyboard=True)
