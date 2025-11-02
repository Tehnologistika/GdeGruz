"""
Utility script to clean up old driver and location data.

This script is based on the original ``cleanup_old_drivers.py`` from the
GdeGruz project.  It has been modified so that certain drivers are never
deleted from the database.  In particular, any driver IDs listed in the
``EXEMPT_USER_IDS`` set will be retained along with all of their location
points.  This allows you to purge stale data for other drivers while
preserving important records (for example, driver ``7552929242``).

Behaviour overview:

* Points older than ``DAYS_THRESHOLD`` days are removed for all non‑exempt
  drivers.
* Drivers who have no remaining points after the purge are removed,
  unless their ID appears in ``EXEMPT_USER_IDS``.
* A summary of the changes is printed both before and after the cleanup.

The script must be run in an environment where the ``db`` module from the
project is importable and the SQLite database exists at the path
``db.DB_PATH``.

Usage::

    python3 cleanup_old_drivers_patched.py

You will be prompted to list all drivers or perform the cleanup.  When
choosing to clean up, the script displays a list of drivers with stale
points and asks for confirmation before deleting anything.
"""

import asyncio
import sys
import os
from datetime import datetime, timezone, timedelta

# ensure we can import the ``db`` module one directory up
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import aiosqlite  # type: ignore
import db  # type: ignore

# Age threshold for deleting location points (in days)
DAYS_THRESHOLD = 7

# Driver IDs that should never be removed from the database
EXEMPT_USER_IDS: set[int] = {7552929242}


async def cleanup_old_data() -> None:
    """Purge stale points and inactive drivers while preserving exempt drivers.

    The cleanup process performs the following steps:

    #. Computes a cutoff date/time ``DAYS_THRESHOLD`` days in the past.
    #. Displays the number of points and drivers before the cleanup.
    #. Identifies drivers whose most recent point is older than the cutoff.
    #. Prompts the user for confirmation to delete these drivers' data.
    #. Deletes points older than the cutoff date for non‑exempt drivers.
    #. Deletes drivers who no longer have any points (again, excluding
       exempt drivers).
    #. Prints statistics about points and drivers after the cleanup.
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=DAYS_THRESHOLD)
    print(f" Очистка данных старше {cutoff_date.strftime('%Y-%m-%d %H:%M')} UTC")
    print("=" * 60)

    async with aiosqlite.connect(db.DB_PATH) as conn:
        # Ensure both points and drivers tables exist
        await db._ensure_schema(conn)
        await db._ensure_driver_schema(conn)

        # 1. Statistics before cleanup
        async with conn.execute("SELECT COUNT(*) FROM points") as cur:
            total_points = (await cur.fetchone())[0]
        async with conn.execute("SELECT COUNT(*) FROM drivers") as cur:
            total_drivers = (await cur.fetchone())[0]
        print(" До очистки:")
        print(f"   Точек: {total_points}")
        print(f"   Водителей: {total_drivers}")
        print()

        # 2. Find drivers with only old points
        # This query returns driver IDs and their most recent timestamp if it
        # falls before the cutoff.  Exempt drivers are filtered out later.
        query_old = """
            SELECT DISTINCT user_id, MAX(ts) as last_ts
            FROM points
            GROUP BY user_id
            HAVING MAX(ts) < ?
        """
        async with conn.execute(query_old, (cutoff_date.isoformat(),)) as cur:
            rows = await cur.fetchall()

        # Filter out exempt drivers from the old drivers list
        old_drivers: list[tuple[int, str]] = [
            (uid, ts) for uid, ts in rows if uid not in EXEMPT_USER_IDS
        ]

        if old_drivers:
            print(f" Найдено {len(old_drivers)} водителей со старыми данными:")
            for user_id, last_ts in old_drivers:
                # Fetch phone number if present
                async with conn.execute(
                    "SELECT phone FROM drivers WHERE user_id = ?",
                    (user_id,),
                ) as cur:
                    phone_row = await cur.fetchone()
                    phone = phone_row[0] if phone_row else "неизвестен"
                print(f"   • ID {user_id} ({phone}), последняя точка: {last_ts}")
        else:
            print("✅ Старых данных не найдено!")
            return

        print()
        response = input("⚠️  Удалить этих водителей и их точки? (yes/no): ")
        if response.lower() != "yes":
            print("❌ Отменено")
            return

        # 3. Delete points older than cutoff for non‑exempt drivers
        # Build a dynamic SQL condition to exclude exempt user IDs from deletion.
        if EXEMPT_USER_IDS:
            # Create a placeholder string like "?, ?, ..." based on count
            placeholders = ", ".join(["?"] * len(EXEMPT_USER_IDS))
            sql_del_points = (
                f"DELETE FROM points WHERE ts < ? AND user_id NOT IN ({placeholders})"
            )
            params: list = [cutoff_date.isoformat(), *EXEMPT_USER_IDS]
        else:
            sql_del_points = "DELETE FROM points WHERE ts < ?"
            params = [cutoff_date.isoformat()]
        await conn.execute(sql_del_points, params)
        deleted_points = conn.total_changes

        # 4. Delete drivers without remaining points (excluding exempt drivers)
        if EXEMPT_USER_IDS:
            placeholders = ", ".join(["?"] * len(EXEMPT_USER_IDS))
            sql_del_drivers = (
                "DELETE FROM drivers "
                "WHERE user_id NOT IN (SELECT DISTINCT user_id FROM points) "
                f"AND user_id NOT IN ({placeholders})"
            )
            params_drivers = [*EXEMPT_USER_IDS]
        else:
            sql_del_drivers = "DELETE FROM drivers WHERE user_id NOT IN (SELECT DISTINCT user_id FROM points)"
            params_drivers = []
        await conn.execute(sql_del_drivers, params_drivers)
        deleted_drivers = conn.total_changes

        await conn.commit()

        # 5. Statistics after cleanup
        async with conn.execute("SELECT COUNT(*) FROM points") as cur:
            remaining_points = (await cur.fetchone())[0]
        async with conn.execute("SELECT COUNT(*) FROM drivers") as cur:
            remaining_drivers = (await cur.fetchone())[0]
        print()
        print("=" * 60)
        print("✅ Очистка завершена!")
        print(f"   Удалено точек: {deleted_points}")
        print(f"   Удалено водителей: {deleted_drivers}")
        print(f"   Осталось точек: {remaining_points}")
        print(f"   Осталось водителей: {remaining_drivers}")


async def list_all_drivers() -> None:
    """Print a list of all drivers with their last known point timestamp."""
    print(" Список всех водителей:")
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
            status = " активен" if active else " неактивен"
            phone_str = phone or "нет номера"
            last_str = last_ts or "нет точек"
            print(
                f"ID {user_id:10} |  {phone_str:15} | {status:12} | последняя точка: {last_str}"
            )


def _menu() -> None:
    """Display a simple CLI menu for listing or cleaning driver data."""
    print(" Утилита очистки данных GdeGruz Bot")
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


if __name__ == "__main__":
    _menu()
