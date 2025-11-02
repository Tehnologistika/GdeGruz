from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def main_kb() -> ReplyKeyboardMarkup:
    """Главная клавиатура бота.

    Содержит три кнопки:
    1) «Поделиться номером»          – запрашивает контакт (телефон)
    2) «Поделиться местоположением»  – запрашивает координаты
    3) «Закончить отслеживание»      – уведомляет диспетчерскую и скрывает клавиатуру
    """
    kb = ReplyKeyboardBuilder()

    # Кнопка запроса телефона
    kb.button(text="Поделиться номером", request_contact=True)
    # Кнопка запроса локации
    kb.button(text="Поделиться местоположением", request_location=True)
    # Кнопка запроса помощи
    kb.button(text="Помощь")
    # Кнопка завершения отслеживания
    kb.button(text="Закончить отслеживание")

    kb.adjust(1, 1, 1, 1)  # каждая кнопка в своей строке
    return kb.as_markup(resize_keyboard=True)


def location_kb() -> ReplyKeyboardMarkup:
    """Клавиатура после того, как водитель поделился номером.

    Кнопки:
    • «Поделиться местоположением»
    • «Закончить отслеживание»
    • «Помощь»
    """
    kb = ReplyKeyboardBuilder()
    kb.button(text="Поделиться местоположением", request_location=True)
    kb.button(text="Закончить отслеживание")
    kb.button(text="Помощь")
    kb.adjust(1, 1, 1)
    return kb.as_markup(resize_keyboard=True)

# ---------------------------------------------------------------------------
# Клавиатура для возобновления отслеживания
# ---------------------------------------------------------------------------

def resume_kb() -> ReplyKeyboardMarkup:
    """Отображается после «Закончить отслеживание».

    Содержит одну кнопку «Возобновить отслеживание».
    """
    kb = ReplyKeyboardBuilder()
    kb.button(text="Возобновить отслеживание")
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)
