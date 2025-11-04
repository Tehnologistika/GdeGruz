"""
Общие функции для работы с базами данных.

Этот модуль содержит функции, используемые несколькими модулями БД,
чтобы избежать циркулярных импортов.
"""

import aiosqlite
from pathlib import Path


async def get_user_id_by_phone_from_db(phone: str, db_path: Path) -> int | None:
    """
    Получить Telegram user_id водителя по номеру телефона.

    Args:
        phone: Номер телефона (+79991234567)
        db_path: Путь к БД drivers

    Returns:
        int | None: Telegram user_id или None если не найден
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path) as conn:
        async with conn.execute("""
            SELECT user_id FROM drivers WHERE phone = ?
        """, (phone,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None
