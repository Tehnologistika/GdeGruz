import asyncio
import db

async def main() -> None:
    await db.clear_all()
    print("Database cleared")

if __name__ == "__main__":
    asyncio.run(main())