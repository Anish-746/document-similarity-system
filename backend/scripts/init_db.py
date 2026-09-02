import asyncio
import asyncpg
from pathlib import Path
import sys

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.core.config import get_settings

async def main():
    settings = get_settings()
    db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    
    print(f"Connecting to database to initialize schema...")
    try:
        conn = await asyncpg.connect(db_url)
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        sys.exit(1)
        
    schema_path = Path(__file__).parent.parent / "schema.sql"
    with open(schema_path, "r") as f:
        schema_sql = f.read()
    
    try:
        await conn.execute(schema_sql)
        print("Schema initialized successfully.")
    except Exception as e:
        print(f"Failed to execute schema.sql: {e}")
        sys.exit(1)
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
