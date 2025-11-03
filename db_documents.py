import logging
from datetime import datetime
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

DB_PATH = Path("/home/git/fleet-live-bot/userdata/documents.db")


async def init_documents_db() -> None:
    """Инициализация БД документов. Создает таблицу и индексы."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        # Создаем таблицу documents
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                trip_id INTEGER,
                doc_type TEXT NOT NULL,
                file_id TEXT NOT NULL,
                file_path TEXT,
                uploaded_at TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'pending'
            )
            """
        )

        # Создаем индекс для пользователя и времени загрузки
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_documents_user
                ON documents(user_id, uploaded_at DESC)
            """
        )

        # Создаем индекс для рейса
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_documents_trip
                ON documents(trip_id)
            """
        )

        await db.commit()
    logger.info("Documents database initialized at %s", DB_PATH)


async def save_document(
    user_id: int,
    doc_type: str,
    file_id: str,
    file_path: str,
    trip_id: int = None,
    description: str = None
) -> int:
    """
    Сохранить документ в БД.

    Args:
        user_id: Telegram ID водителя
        doc_type: Тип документа (loading_photo, unloading_photo, ttn, invoice, acceptance_act)
        file_id: Telegram file_id для доступа к файлу
        file_path: Путь к сохраненному файлу на диске
        trip_id: ID рейса (опционально)
        description: Описание документа (опционально)

    Returns:
        int: ID созданного документа
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        uploaded_at = datetime.now().isoformat()
        cursor = await db.execute(
            """
            INSERT INTO documents(user_id, trip_id, doc_type, file_id, file_path, uploaded_at, description, status)
            VALUES(?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            (user_id, trip_id, doc_type, file_id, file_path, uploaded_at, description),
        )
        await db.commit()
        doc_id = cursor.lastrowid
    logger.info(f"Saved document {doc_type} for user {user_id}")
    return doc_id


async def get_user_documents(user_id: int, doc_type: str = None) -> list[dict]:
    """
    Получить документы пользователя.

    Args:
        user_id: Telegram ID водителя
        doc_type: Фильтр по типу (опционально)

    Returns:
        list[dict]: Список документов с полями id, doc_type, file_id, file_path, uploaded_at, status
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        if doc_type:
            query = """
                SELECT id, doc_type, file_id, file_path, uploaded_at, status
                FROM documents
                WHERE user_id = ? AND doc_type = ?
                ORDER BY uploaded_at DESC
            """
            params = (user_id, doc_type)
        else:
            query = """
                SELECT id, doc_type, file_id, file_path, uploaded_at, status
                FROM documents
                WHERE user_id = ?
                ORDER BY uploaded_at DESC
            """
            params = (user_id,)

        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()

        return [
            {
                "id": row[0],
                "doc_type": row[1],
                "file_id": row[2],
                "file_path": row[3],
                "uploaded_at": row[4],
                "status": row[5],
            }
            for row in rows
        ]


async def get_trip_documents(trip_id: int) -> list[dict]:
    """
    Получить все документы по рейсу.

    Args:
        trip_id: ID рейса

    Returns:
        list[dict]: Список документов с полями id, user_id, doc_type, file_id, file_path, uploaded_at, status
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        query = """
            SELECT id, user_id, doc_type, file_id, file_path, uploaded_at, status
            FROM documents
            WHERE trip_id = ?
            ORDER BY uploaded_at
        """
        async with db.execute(query, (trip_id,)) as cursor:
            rows = await cursor.fetchall()

        return [
            {
                "id": row[0],
                "user_id": row[1],
                "doc_type": row[2],
                "file_id": row[3],
                "file_path": row[4],
                "uploaded_at": row[5],
                "status": row[6],
            }
            for row in rows
        ]


async def get_active_trip(user_id: int) -> int | None:
    """
    Получить ID активного рейса водителя.

    ВРЕМЕННАЯ ЗАГЛУШКА - всегда возвращает None.
    Будет реализовано в Этапе 2.

    Args:
        user_id: Telegram ID водителя

    Returns:
        int | None: ID активного рейса или None
    """
    # ЗАГЛУШКА: return None
    # TODO: Реализовать в Этапе 2 после создания таблицы trips
    return None
