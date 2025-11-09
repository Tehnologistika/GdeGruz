#!/usr/bin/env python3
"""
СРОЧНАЯ очистка БД - запуск напрямую на сервере.
Просто удаляет ВСЕ рейсы из базы данных.
"""

import sqlite3
import sys
from pathlib import Path

def cleanup():
    # Ищем БД
    possible_paths = [
        Path("data/trips.db"),
        Path("trips.db"),
        Path("/app/data/trips.db"),
        Path("/app/trips.db"),
    ]

    db_path = None
    for p in possible_paths:
        if p.exists():
            db_path = p
            print(f"✅ Найдена БД: {db_path}")
            break

    if not db_path:
        print("❌ База данных trips.db не найдена!")
        return False

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Считаем сколько рейсов
        cursor.execute("SELECT COUNT(*) FROM trips")
        count = cursor.fetchone()[0]
        print(f"🔍 Найдено рейсов: {count}")

        if count == 0:
            print("✅ Рейсов нет")
            return True

        # Показываем статистику
        cursor.execute("SELECT status, COUNT(*) FROM trips GROUP BY status")
        for status, cnt in cursor.fetchall():
            print(f"  • {status}: {cnt}")

        # УДАЛЯЕМ ВСЕ
        print("🗑️  Удаляем ВСЕ рейсы...")
        cursor.execute("DELETE FROM trips")

        # Очищаем события
        try:
            cursor.execute("DELETE FROM trip_events")
            print("  • Очищена trip_events")
        except:
            pass

        # Сбрасываем счетчик
        try:
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='trips'")
            print("  • Сброшен автоинкремент")
        except:
            pass

        conn.commit()

        # Проверяем
        cursor.execute("SELECT COUNT(*) FROM trips")
        remaining = cursor.fetchone()[0]

        conn.close()

        if remaining == 0:
            print(f"✅ Успешно удалено {count} рейсов!")
            return True
        else:
            print(f"❌ ОШИБКА! Осталось {remaining} рейсов!")
            return False

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

if __name__ == "__main__":
    success = cleanup()
    sys.exit(0 if success else 1)
