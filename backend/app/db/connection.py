import asyncpg
from typing import AsyncGenerator

from app.core.config import get_settings

_pool: asyncpg.Pool | None = None

async def init_db_pool() -> None:
    global _pool
    settings = get_settings()
    # asyncpg uses postgresql:// instead of postgresql+asyncpg://
    db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    _pool = await asyncpg.create_pool(
        dsn=db_url,
        min_size=10,
        max_size=20,
    )

async def close_db_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None

async def get_db_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """FastAPI dependency that yields a per-request database connection."""
    if _pool is None:
        raise RuntimeError("Database pool is not initialized")
    
    async with _pool.acquire() as conn:
        # Provide connection with automatic transaction management (like get_db did)
        # Using a transaction ensures auto-rollback on exception
        async with conn.transaction():
            yield conn
