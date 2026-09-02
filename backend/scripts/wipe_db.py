import asyncio
import asyncpg
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.core.config import get_settings

async def main():
    settings = get_settings()
    db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(db_url)
    await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    print("Database wiped.")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
