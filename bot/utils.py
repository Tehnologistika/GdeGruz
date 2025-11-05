"""
Вспомогательные функции для бота.
"""
import os
import logging

logger = logging.getLogger(__name__)


def is_curator(user_id: int) -> bool:
    """
    Проверяет, является ли пользователь куратором рейсов.

    Args:
        user_id: Telegram user ID

    Returns:
        bool: True если пользователь куратор, False если водитель
    """
    curator_ids_str = os.getenv("CURATOR_IDS", "")
    curator_ids = [int(x.strip()) for x in curator_ids_str.split(",") if x.strip()]
    result = user_id in curator_ids

    logger.info(
        "Role check: user_id=%s, CURATOR_IDS='%s', parsed_ids=%s, is_curator=%s",
        user_id, curator_ids_str, curator_ids, result
    )

    return result
