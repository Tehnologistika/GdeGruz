from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def location_kb() -> ReplyKeyboardMarkup:
    """Keyboard with a single button requesting location."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="Share location", request_location=True)
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)
