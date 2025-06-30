import logging

from aiogram.types import Message

from ..keyboards import location_kb

logger = logging.getLogger(__name__)


async def start(message: Message) -> None:
    """Handle /start command."""
    logger.info("User %s started bot", message.from_user.id if message.from_user else "unknown")
    await message.answer("Please share your location", reply_markup=location_kb())
