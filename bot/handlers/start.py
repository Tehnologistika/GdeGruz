import logging
import os

from aiogram.types import Message, ReplyKeyboardRemove

from ..keyboards import main_kb

logger = logging.getLogger(__name__)

# Telegram ID кураторов (из переменных окружения)
CURATOR_IDS = [int(x) for x in os.getenv("CURATOR_IDS", "").split(",") if x]


def is_curator(user_id: int) -> bool:
    """Проверка, является ли пользователь куратором."""
    return user_id in CURATOR_IDS


async def start(message: Message) -> None:
    """Handle /start command."""
    user_id = message.from_user.id if message.from_user else 0
    logger.info("User %s started bot", user_id)

    # Проверяем роль пользователя
    if is_curator(user_id):
        logger.info("User %s is curator, removing reply keyboard", user_id)

        # Куратор - сначала удаляем постоянные кнопки
        await message.answer(
            "🔄 Обновление интерфейса...",
            reply_markup=ReplyKeyboardRemove()
        )

        # Показываем панель управления (только инлайн кнопки)
        from aiogram.utils.keyboard import InlineKeyboardBuilder

        kb = InlineKeyboardBuilder()
        kb.button(text="➕ Создать рейс", callback_data="new_trip")
        kb.button(text="📋 Активные рейсы", callback_data="list_active_trips")
        kb.button(text="🎛 Панель управления", callback_data="back_to_admin")
        kb.adjust(1)

        await message.answer(
            "🎛 <b>Панель куратора рейсов</b>\n\n"
            "Добро пожаловать в систему управления рейсами ГдеГруз!\n\n"
            "Используйте кнопки ниже или команды:\n"
            "/admin - панель управления\n"
            "/trips - список рейсов\n"
            "/create_trip - создать рейс",
            parse_mode="HTML",
            reply_markup=kb.as_markup(),
        )
    else:
        logger.info("User %s is driver", user_id)
        # Водитель - показываем инструкцию
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
