import logging

from aiogram.types import Message, ReplyKeyboardMarkup
from aiogram.filters import Command
from aiogram import Router

from ..keyboards import main_kb, curator_kb
from ..utils import is_curator

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("myid"))
async def get_my_id(message: Message) -> None:
    """Получить свой Telegram ID."""
    user_id = message.from_user.id if message.from_user else 0
    user_name = message.from_user.full_name if message.from_user else "Unknown"
    username = message.from_user.username if message.from_user else "нет"

    await message.answer(
        f"<b>Ваш Telegram ID:</b>\n\n"
        f"🆔 <code>{user_id}</code>\n\n"
        f"👤 Имя: {user_name}\n"
        f"📝 Username: @{username}\n\n"
        f"<i>Чтобы стать куратором, добавьте этот ID в CURATOR_IDS в файле .env</i>",
        parse_mode="HTML"
    )


@router.message(Command("start"))
async def start(message: Message) -> None:
    """Handle /start command."""
    user_id = message.from_user.id if message.from_user else 0
    user_name = message.from_user.full_name if message.from_user else "Unknown"
    logger.info("User %s (%s) started bot", user_id, user_name)

    # Проверяем роль пользователя
    if is_curator(user_id):
        # Куратор - даём админ-панель сразу
        logger.info("User %s identified as CURATOR - showing curator keyboard", user_id)
        await message.answer(
            "🎛 <b>Добро пожаловать, куратор!</b>\n\n"
            "Вы получили доступ к панели управления рейсами.\n\n"
            "Используйте кнопки ниже для управления:",
            reply_markup=curator_kb(),
            parse_mode="HTML",
        )
    else:
        # Водитель - просим поделиться номером
        logger.info("User %s identified as DRIVER - showing phone request", user_id)
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
            "   • Нажимайте эту кнопку каждые 24 часа, чтобы мы знали, где находится машина.\n\n"
            "🕑 Если забудете — я напомню.\n\n"
            "Счастливого пути! 🚚",
            parse_mode="HTML",
        )
