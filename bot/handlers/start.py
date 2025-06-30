import logging

from aiogram.types import Message, ReplyKeyboardMarkup

from ..keyboards import main_kb

logger = logging.getLogger(__name__)


async def start(message: Message) -> ReplyKeyboardMarkup:
    """Handle /start command."""
    logger.info("User %s started bot", message.from_user.id if message.from_user else "unknown")
    await message.answer(
        "Пожалуйста, сначала нажмите «Поделиться номерoм», а затем «Поделиться местоположением».",
        reply_markup=main_kb(),
    )

    # приветственное сообщение и инструкция
    await message.answer(
        "Компания <b>Технологистика</b> желает вам счастливого пути! 🚚\n"
        "• Сначала поделитесь номером телефона, чтобы диспетчеру было проще вас узнать.\n"
        "• Затем нажимайте «Поделиться местоположением» <u>каждые 12 часов</u>.\n"
        "• Если забудете, я пришлю напоминание.",
        parse_mode="HTML",
    )
