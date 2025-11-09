"""
КРИТИЧЕСКАЯ УЯЗВИМОСТЬ БЕЗОПАСНОСТИ!
Команда /redeploy отключена из-за риска RCE (Remote Code Execution).

Используйте GitHub Actions для автоматического деплоя вместо этого.
"""

import logging
from aiogram.types import Message

logger = logging.getLogger(__name__)


async def redeploy(message: Message) -> None:
    """
    Команда отключена по соображениям безопасности.
    Используйте GitHub Actions для деплоя.
    """
    await message.answer(
        "⚠️ Команда /redeploy отключена по соображениям безопасности.\n\n"
        "Деплой происходит автоматически через GitHub Actions.\n"
        "Просто запушьте изменения в репозиторий."
    )
    logger.warning(
        "Attempt to use disabled /redeploy command by user %s",
        message.from_user.id if message.from_user else "unknown"
    )

