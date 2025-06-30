import logging

from aiogram.types import Message, ReplyKeyboardMarkup

from ..keyboards import location_kb

logger = logging.getLogger(__name__)


async def start(message: Message) -> ReplyKeyboardMarkup:
    """Handle /start command."""
    logger.info("User %s started bot", message.from_user.id if message.from_user else "unknown")
    keyboard = location_kb()
    await message.answer("Please share your location", reply_markup=keyboard)
    await message.answer(
        "Компания <b>Технологистика</b> желает вам счастливого пути!\n"
        "• Нажимайте «<Поделиться местоположением>» <u>каждые 24 ч</u>,\n"
        "  чтобы мы знали, где находится автомобиль.\n"
        "• Не переживайте, если забудете — бот сам напомнит.\n"
        "• Live-локация передаётся автоматически каждый час.",
        parse_mode="HTML",
    )
    return keyboard
