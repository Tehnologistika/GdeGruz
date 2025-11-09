#!/usr/bin/env python3
"""
Скрипт для очистки тестовых данных из базы данных.

Очищает:
- Все рейсы (trips.db)
- Все документы (documents.db)
- Опционально: координаты водителей (points.db)

Водители (drivers) НЕ удаляются - остаются зарегистрированными.
"""

import asyncio
import aiosqlite
import os
import sys
import logging
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Пути к базам данных
# Ищем в текущей директории или в data/
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

# Проверяем разные возможные пути
def find_db_path(db_name: str) -> Path:
    """Находит путь к базе данных."""
    possible_paths = [
        DATA_DIR / db_name,  # ./data/trips.db
        BASE_DIR / db_name,  # ./trips.db
        Path("/app/data") / db_name,  # Docker: /app/data/trips.db
        Path("/app") / db_name,  # Docker: /app/trips.db
    ]

    for path in possible_paths:
        if path.exists():
            logger.info(f"✅ Найдена БД: {path}")
            return path

    # Возвращаем путь по умолчанию
    logger.warning(f"⚠️ БД {db_name} не найдена, используется путь по умолчанию: {DATA_DIR / db_name}")
    return DATA_DIR / db_name

TRIPS_DB = find_db_path("trips.db")
DOCUMENTS_DB = find_db_path("documents.db")
POINTS_DB = find_db_path("points.db")


async def cleanup_trips():
    """Очистка всех рейсов."""
    if not TRIPS_DB.exists():
        logger.warning(f"База данных {TRIPS_DB} не найдена, пропускаем")
        return 0

    logger.info(f"📂 Открываем БД: {TRIPS_DB}")

    async with aiosqlite.connect(TRIPS_DB) as db:
        # Подсчитываем количество рейсов перед удалением
        async with db.execute("SELECT COUNT(*) FROM trips") as cursor:
            count = (await cursor.fetchone())[0]

        if count == 0:
            logger.info("✅ Рейсов в базе нет, очистка не требуется")
            return 0

        logger.info(f"🔍 Найдено рейсов для удаления: {count}")

        # Показываем статистику по статусам
        try:
            async with db.execute("SELECT status, COUNT(*) FROM trips GROUP BY status") as cursor:
                rows = await cursor.fetchall()
                for status, cnt in rows:
                    logger.info(f"  • {status}: {cnt} рейс(ов)")
        except Exception as e:
            logger.warning(f"Не удалось получить статистику: {e}")

        # Удаляем ВСЕ рейсы (без фильтров!)
        logger.info("🗑️  Удаляем ВСЕ рейсы...")
        result = await db.execute("DELETE FROM trips")
        logger.info(f"  Удалено строк: {result.rowcount if hasattr(result, 'rowcount') else 'N/A'}")

        # Очищаем события рейсов (если таблица существует)
        try:
            async with db.execute("SELECT COUNT(*) FROM trip_events") as cursor:
                events_count = (await cursor.fetchone())[0]

            if events_count > 0:
                await db.execute("DELETE FROM trip_events")
                logger.info(f"  • Удалено {events_count} событий из trip_events")
        except aiosqlite.OperationalError:
            # Таблица может не существовать
            logger.debug("  • Таблица trip_events не найдена (это нормально)")

        # Сбрасываем автоинкремент
        try:
            await db.execute("DELETE FROM sqlite_sequence WHERE name='trips'")
            logger.info("  • Сброшен счетчик автоинкремента")
        except Exception:
            pass

        await db.commit()

        # Проверяем что действительно все удалено
        async with db.execute("SELECT COUNT(*) FROM trips") as cursor:
            remaining = (await cursor.fetchone())[0]

        if remaining == 0:
            logger.info(f"✅ Успешно удалено {count} рейсов из {TRIPS_DB}")
        else:
            logger.error(f"❌ ОШИБКА! Осталось {remaining} рейсов после очистки!")

        return count


async def cleanup_documents():
    """Очистка всех документов."""
    if not DOCUMENTS_DB.exists():
        logger.warning(f"База данных {DOCUMENTS_DB} не найдена, пропускаем")
        return 0

    async with aiosqlite.connect(DOCUMENTS_DB) as db:
        # Подсчитываем количество документов
        async with db.execute("SELECT COUNT(*) FROM documents") as cursor:
            count = (await cursor.fetchone())[0]

        if count == 0:
            logger.info("✅ Документов в базе нет, очистка не требуется")
            return 0

        # Удаляем все документы
        await db.execute("DELETE FROM documents")
        await db.commit()
        logger.info(f"✅ Удалено {count} документов из documents.db")
        return count


async def cleanup_points():
    """Очистка координат водителей (опционально)."""
    if not POINTS_DB.exists():
        logger.warning(f"База данных {POINTS_DB} не найдена, пропускаем")
        return 0

    async with aiosqlite.connect(POINTS_DB) as db:
        # Подсчитываем количество точек
        async with db.execute("SELECT COUNT(*) FROM points") as cursor:
            count = (await cursor.fetchone())[0]

        if count == 0:
            logger.info("✅ Координат в базе нет, очистка не требуется")
            return 0

        # Удаляем все координаты
        await db.execute("DELETE FROM points")
        await db.commit()
        logger.info(f"✅ Удалено {count} записей координат из points.db")
        return count


async def cleanup_all(include_points: bool = False):
    """
    Очистка всех тестовых данных.

    Args:
        include_points: Если True, также очистит координаты водителей
    """
    logger.info("🧹 Начинаем очистку тестовых данных...")
    logger.info(f"📁 Директория данных: {DATA_DIR}")

    if not DATA_DIR.exists():
        logger.error(f"❌ Директория {DATA_DIR} не найдена!")
        return False

    try:
        # Очищаем рейсы
        trips_count = await cleanup_trips()

        # Очищаем документы
        docs_count = await cleanup_documents()

        # Опционально очищаем координаты
        points_count = 0
        if include_points:
            points_count = await cleanup_points()
        else:
            logger.info("ℹ️  Координаты водителей НЕ удаляются (используйте --all для полной очистки)")

        # Итоги
        logger.info("")
        logger.info("=" * 60)
        logger.info("📊 ИТОГИ ОЧИСТКИ:")
        logger.info(f"  • Рейсов удалено: {trips_count}")
        logger.info(f"  • Документов удалено: {docs_count}")
        if include_points:
            logger.info(f"  • Координат удалено: {points_count}")
        logger.info("=" * 60)
        logger.info("✅ Очистка завершена успешно!")

        return True

    except Exception as e:
        logger.error(f"❌ Ошибка при очистке: {e}", exc_info=True)
        return False


def main():
    """Главная функция."""
    # Проверяем аргументы командной строки
    include_points = "--all" in sys.argv or "--points" in sys.argv

    if "--help" in sys.argv or "-h" in sys.argv:
        print("Использование: python cleanup_test_data.py [опции]")
        print("")
        print("Опции:")
        print("  --all, --points    Также удалить координаты водителей")
        print("  --help, -h         Показать эту справку")
        print("")
        print("По умолчанию:")
        print("  - Удаляются все рейсы")
        print("  - Удаляются все документы")
        print("  - Водители остаются зарегистрированными")
        print("  - Координаты НЕ удаляются")
        return

    # Запускаем очистку
    success = asyncio.run(cleanup_all(include_points=include_points))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
