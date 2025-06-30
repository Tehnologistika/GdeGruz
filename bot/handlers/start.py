import logging

from aiogram.types import Message, ReplyKeyboardMarkup

from ..keyboards import main_kb

logger = logging.getLogger(__name__)


async def start(message: Message) -> ReplyKeyboardMarkup:
    """Handle /start command."""
    logger.info("User %s started bot", message.from_user.id if message.from_user else "unknown")
    await message.answer(
        "Пожалуйста, сначала нажмите «Поделиться номером», а затем «Поделиться местоположением».",
        reply_markup=main_kb(),
    )

    # приветственное сообщение и инструкция
    await message.answer(
        "🚀 <b>Добро пожаловать в Технологистику!</b>\n\n"
        "1️⃣ <b>Поделиться номером</b>\n"
        "   • Нажмите кнопку, чтобы диспетчеры сразу видели, кто на связи.\n\n"
        "2️⃣ <b>Поделиться местоположением</b>\n"
        "   • Нажимайте эту кнопку каждые 12 часов, чтобы мы знали, где находится машина.\n\n"
        "🕑 Если забудете — я напомню.\n\n"
        "Счастливого пути! 🚚",
        parse_mode="HTML",
    )
