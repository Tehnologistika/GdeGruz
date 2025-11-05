"""
Вспомогательные функции для бота.
"""
import os


def is_curator(user_id: int) -> bool:
    """
    Проверяет, является ли пользователь куратором рейсов.

    Args:
        user_id: Telegram user ID

    Returns:
        bool: True если пользователь куратор, False если водитель
    """
    curator_ids_str = os.getenv("CURATOR_IDS", "")
    curator_ids = [int(x) for x in curator_ids_str.split(",") if x]
    return user_id in curator_ids
