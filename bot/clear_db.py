import asyncio, os, sys
# make parent directory importable to resolve `import db`
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import db

async def main() -> None:
    await db.clear_all()
    print("Database cleared")

if __name__ == "__main__":
    asyncio.run(main())