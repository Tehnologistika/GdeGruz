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
DATA_DIR = Path(__file__).parent / "data"
TRIPS_DB = DATA_DIR / "trips.db"
DOCUMENTS_DB = DATA_DIR / "documents.db"
POINTS_DB = DATA_DIR / "points.db"


async def cleanup_trips():
    """Очистка всех рейсов."""
    if not TRIPS_DB.exists():
        logger.warning(f"База данных {TRIPS_DB} не найдена, пропускаем")
        return 0

    async with aiosqlite.connect(TRIPS_DB) as db:
        # Подсчитываем количество рейсов перед удалением
        async with db.execute("SELECT COUNT(*) FROM trips") as cursor:
            count = (await cursor.fetchone())[0]

        if count == 0:
            logger.info("✅ Рейсов в базе нет, очистка не требуется")
            return 0

        # Удаляем все рейсы
        await db.execute("DELETE FROM trips")

        # Очищаем события рейсов (если таблица существует)
        try:
            await db.execute("DELETE FROM trip_events")
            logger.info("  - Очищена таблица trip_events")
        except aiosqlite.OperationalError:
            # Таблица может не существовать
            pass

        await db.commit()
        logger.info(f"✅ Удалено {count} рейсов из trips.db")
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
