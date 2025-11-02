import asyncio
import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import aiosqlite
import db

# Удалить точки старше этого периода (дни)
DAYS_THRESHOLD = 7


async def cleanup_old_data():
    """
    Очистка старых данных:
    1. Удаляет точки старше DAYS_THRESHOLD дней
    2. Удаляет водителей без точек
    3. Показывает статистику
    """
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=DAYS_THRESHOLD)
    print(f"🧹 Очистка данных старше {cutoff_date.strftime('%Y-%m-%d %H:%M')} UTC")
    print("=" * 60)
    
    async with aiosqlite.connect(db.DB_PATH) as conn:
        await db._ensure_schema(conn)
        await db._ensure_driver_schema(conn)
        
        # 1. Статистика ДО очистки
        async with conn.execute("SELECT COUNT(*) FROM points") as cur:
            total_points = (await cur.fetchone())[0]
        
        async with conn.execute("SELECT COUNT(*) FROM drivers") as cur:
            total_drivers = (await cur.fetchone())[0]
        
        print(f"📊 До очистки:")
        print(f"   Точек: {total_points}")
        print(f"   Водителей: {total_drivers}")
        print()
        
        # 2. Найти водителей со старыми точками
        query_old = """
            SELECT DISTINCT user_id, MAX(ts) as last_ts
            FROM points
            GROUP BY user_id
            HAVING MAX(ts) < ?
        """
        async with conn.execute(query_old, (cutoff_date.isoformat(),)) as cur:
            old_drivers = await cur.fetchall()
        
        if old_drivers:
            print(f"🔍 Найдено {len(old_drivers)} водителей со старыми данными:")
            for user_id, last_ts in old_drivers:
                # Получаем телефон если есть
                async with conn.execute(
                    "SELECT phone FROM drivers WHERE user_id = ?", (user_id,)
                ) as cur:
                    phone_row = await cur.fetchone()
                    phone = phone_row[0] if phone_row else "неизвестен"
                
                print(f"   • ID {user_id} (📞 {phone}), последняя точка: {last_ts}")
        else:
            print("✅ Старых данных не найдено!")
            return
        
        print()
        response = input("⚠️  Удалить этих водителей и их точки? (yes/no): ")
        
        if response.lower() != "yes":
            print("❌ Отменено")
            return
        
        # 3. Удаление старых точек
        await conn.execute(
            "DELETE FROM points WHERE ts < ?",
            (cutoff_date.isoformat(),)
        )
        deleted_points = conn.total_changes
        
        # 4. Удаление водителей без точек
        await conn.execute("""
            DELETE FROM drivers
            WHERE user_id NOT IN (SELECT DISTINCT user_id FROM points)
        """)
        deleted_drivers = conn.total_changes
        
        await conn.commit()
        
        # 5. Статистика ПОСЛЕ
        async with conn.execute("SELECT COUNT(*) FROM points") as cur:
            remaining_points = (await cur.fetchone())[0]
        
        async with conn.execute("SELECT COUNT(*) FROM drivers") as cur:
            remaining_drivers = (await cur.fetchone())[0]
        
        print()
        print("=" * 60)
        print(f"✅ Очистка завершена!")
        print(f"   Удалено точек: {deleted_points}")
        print(f"   Удалено водителей: {deleted_drivers}")
        print(f"   Осталось точек: {remaining_points}")
        print(f"   Осталось водителей: {remaining_drivers}")


async def list_all_drivers():
    """Показать всех водителей с последними точками"""
    print("📋 Список всех водителей:")
    print("=" * 60)
    
    async with aiosqlite.connect(db.DB_PATH) as conn:
        await db._ensure_schema(conn)
        await db._ensure_driver_schema(conn)
        
        query = """
            SELECT 
                d.user_id,
                d.phone,
                d.active,
                MAX(p.ts) as last_point_ts
            FROM drivers d
            LEFT JOIN points p ON d.user_id = p.user_id
            GROUP BY d.user_id
            ORDER BY last_point_ts DESC NULLS LAST
        """
        
        async with conn.execute(query) as cur:
            rows = await cur.fetchall()
        
        if not rows:
            print("Нет водителей в БД")
            return
        
        for user_id, phone, active, last_ts in rows:
            status = "🟢 активен" if active else "🔴 неактивен"
            phone_str = phone or "нет номера"
            last_str = last_ts or "нет точек"
            
            print(f"ID {user_id:10} | 📞 {phone_str:15} | {status:12} | последняя точка: {last_str}")


if __name__ == "__main__":
    print("🤖 Утилита очистки данных GdeGruz Bot")
    print()
    print("Выберите действие:")
    print("1. Показать всех водителей")
    print("2. Очистить старые данные")
    print()
    
    choice = input("Введите номер (1 или 2): ").strip()
    
    if choice == "1":
        asyncio.run(list_all_drivers())
    elif choice == "2":
        asyncio.run(cleanup_old_data())
    else:
        print("❌ Неверный выбор")