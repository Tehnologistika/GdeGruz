from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def location_kb() -> ReplyKeyboardMarkup:
    """Keyboard with contact and location buttons."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="Поделиться номером", request_contact=True)
    builder.button(text="Поделиться местоположением", request_location=True)
    builder.adjust(1, 1)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)
