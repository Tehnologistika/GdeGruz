import asyncio
import logging
import os

from aiogram.filters import Command
from aiogram.types import Message

logger = logging.getLogger(__name__)

# Поддержка нескольких администраторов (через запятую)
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_ID", "0").split(",") if x.strip()]


async def redeploy(message: Message) -> None:
    """Redeploy the bot container (admin only)."""
    if not message.from_user or message.from_user.id not in ADMIN_IDS:
        await message.answer("Unauthorized")
        return

    await message.answer("Redeploying...")
    proc = await asyncio.create_subprocess_shell(
        "cd ~/fleet-live-bot && git pull && docker compose up -d",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    output = stdout.decode().strip()
    if not output:
        output = "done"
    await message.answer(f"`{output}`", parse_mode="Markdown")
    logger.info("Redeploy command executed by %s", message.from_user.id)

