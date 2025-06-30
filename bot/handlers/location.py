import logging

from aiogram import F, Router
from aiogram.types import Message

from ..storage import save_point


logger = logging.getLogger(__name__)

# Router that holds all location handlers
router = Router()


@router.message(F.location)
@router.edited_message(F.location)
async def handle_location(msg: Message) -> None:
    """Handle both static and live location updates."""
    user_id = msg.from_user.id if msg.from_user else 0
    lat = msg.location.latitude
    lon = msg.location.longitude

    logger.info("Received location from %s: %s, %s", user_id, lat, lon)
    await save_point(user_id, lat, lon, msg.date)

    if msg.location.live_period:
        await msg.answer("Спасибо! Получаю вашу live-локацию.")
    else:
        await msg.answer("Спасибо! Точка получена.")
