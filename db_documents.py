"""
Модуль для работы с базой данных документов.

Этот модуль обеспечивает сохранение и управление документами водителей.
"""

import aiosqlite
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)
DB_PATH = Path("/app/data/documents.db")

# Типы документов
DOC_TYPES = {
    "loading_photo": "📸 Фото погрузки",
    "unloading_photo": "📸 Фото выгрузки",
    "ttn": "📄 ТТН",
    "upd": "📄 УПД",
    "other": "📄 Другой документ"
}


async def init_documents_db() -> None:
    """Инициализация БД документов. Создает таблицы и индексы."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        # Создать таблицу documents
        await db.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                trip_id INTEGER,
                doc_type TEXT NOT NULL,
                file_id TEXT NOT NULL,
                file_path TEXT,
                telegram_msg_id INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY (trip_id) REFERENCES trips(trip_id)
            )
        """)

        # Создать индексы
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_documents_user ON documents(user_id)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_documents_trip ON documents(trip_id)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(doc_type)
        """)

        await db.commit()

    logger.info("Documents database initialized")


async def save_document(
    user_id: int,
    doc_type: str,
    file_id: str,
    file_path: Optional[str] = None,
    telegram_msg_id: Optional[int] = None,
    trip_id: Optional[int] = None
) -> int:
    """
    Сохранить документ в БД.

    Args:
        user_id: Telegram ID водителя
        doc_type: Тип документа (loading_photo, unloading_photo, ttn, upd, other)
        file_id: Telegram file_id
        file_path: Путь к сохраненному файлу на диске (опционально)
        telegram_msg_id: ID сообщения в группе документов (опционально)
        trip_id: ID рейса (опционально, автоматически определяется если None)

    Returns:
        int: ID созданного документа
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_schema(db)

        # Если trip_id не указан, пытаемся получить активный рейс
        if trip_id is None:
            trip_id = await get_active_trip(user_id)

        cursor = await db.execute("""
            INSERT INTO documents (
                user_id, trip_id, doc_type, file_id, file_path,
                telegram_msg_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, trip_id, doc_type, file_id, file_path,
            telegram_msg_id, datetime.now().isoformat()
        ))

        doc_id = cursor.lastrowid
        await db.commit()

        # Логируем событие в рейс (если есть привязка)
        if trip_id:
            try:
                import db_trips
                await db_trips.log_trip_event(
                    trip_id=trip_id,
                    event_type="document_uploaded",
                    description=f"Загружен документ: {DOC_TYPES.get(doc_type, doc_type)}",
                    created_by=user_id,
                    metadata={"doc_id": doc_id, "doc_type": doc_type}
                )
            except Exception as e:
                logger.warning(f"Failed to log trip event for document {doc_id}: {e}")

    logger.info(f"Saved document {doc_type} (ID: {doc_id}) for user {user_id}, trip {trip_id}")
    return doc_id


async def get_document(doc_id: int) -> Optional[Dict[str, Any]]:
    """
    Получить информацию о документе по ID.

    Args:
        doc_id: ID документа

    Returns:
        Dict | None: Словарь с информацией о документе или None если не найден
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_schema(db)
        db.row_factory = aiosqlite.Row

        async with db.execute("""
            SELECT * FROM documents WHERE id = ?
        """, (doc_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)

    return None


async def get_user_documents(
    user_id: int,
    doc_type: Optional[str] = None,
    trip_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Получить документы водителя.

    Args:
        user_id: Telegram ID водителя
        doc_type: Фильтр по типу документа (опционально)
        trip_id: Фильтр по рейсу (опционально)

    Returns:
        List[Dict]: Список документов
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_schema(db)
        db.row_factory = aiosqlite.Row

        query = "SELECT * FROM documents WHERE user_id = ?"
        params = [user_id]

        if doc_type:
            query += " AND doc_type = ?"
            params.append(doc_type)

        if trip_id:
            query += " AND trip_id = ?"
            params.append(trip_id)

        query += " ORDER BY created_at DESC"

        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_trip_documents(trip_id: int) -> List[Dict[str, Any]]:
    """
    Получить все документы по рейсу.

    Args:
        trip_id: ID рейса

    Returns:
        List[Dict]: Список документов рейса
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_schema(db)
        db.row_factory = aiosqlite.Row

        async with db.execute("""
            SELECT * FROM documents
            WHERE trip_id = ?
            ORDER BY created_at ASC
        """, (trip_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_active_trip(user_id: int) -> Optional[int]:
    """
    Получить ID активного рейса водителя.

    Логика: возвращает ID первого найденного активного рейса
    (статус не 'completed' и не 'cancelled').

    Args:
        user_id: Telegram ID водителя

    Returns:
        int | None: ID активного рейса или None
    """
    try:
        import db_trips

        trips = await db_trips.get_user_active_trips(user_id)
        if trips:
            # Возвращаем первый активный рейс
            return trips[0]['trip_id']
    except Exception as e:
        logger.warning(f"Failed to get active trip for user {user_id}: {e}")

    return None


async def update_document_trip(doc_id: int, trip_id: int) -> None:
    """
    Обновить привязку документа к рейсу.

    Args:
        doc_id: ID документа
        trip_id: ID рейса
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_schema(db)

        await db.execute("""
            UPDATE documents SET trip_id = ? WHERE id = ?
        """, (trip_id, doc_id))
        await db.commit()

    logger.info(f"Updated document {doc_id} trip to {trip_id}")


async def delete_document(doc_id: int) -> bool:
    """
    Удалить документ из БД.

    Args:
        doc_id: ID документа

    Returns:
        bool: True если документ был удален, False если не найден
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_schema(db)

        cursor = await db.execute("""
            DELETE FROM documents WHERE id = ?
        """, (doc_id,))
        await db.commit()

        return cursor.rowcount > 0


async def _ensure_schema(db: aiosqlite.Connection) -> None:
    """Вспомогательная функция для обеспечения наличия схемы БД."""
    # Проверить, что таблица существует
    cursor = await db.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='documents'
    """)
    tables = await cursor.fetchall()

    if len(tables) == 0:
        # Пере-инициализируем БД если таблицы нет
        logger.warning("Documents database table not found, re-initializing...")
        await init_documents_db()
