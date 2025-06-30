import logging
from datetime import datetime, timezone

from aiogram.types import Message

from ..storage import save_point

logger = logging.getLogger(__name__)


async def location(message: Message) -> None:
    """Handle incoming location messages."""
    if not message.location:
        return

    user_id = message.from_user.id if message.from_user else 0
    lat = message.location.latitude
    lon = message.location.longitude
    ts = datetime.now(timezone.utc)

    logger.info("Received location from %s: %s, %s", user_id, lat, lon)
    await save_point(user_id=user_id, lat=lat, lon=lon, ts=ts)
    await message.answer("Location saved")
