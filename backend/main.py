"""
main.py -- FastAPI application entry point.

Startup sequence:
  1. Validate settings (b*r == n, env vars present).
  2. Create the async database engine (connection pool).
  3. Connect to Redis (lazy — first command establishes the connection).
  4. Mount routers.
  5. Configure CORS (allow Vite dev server on port 5173).

Shutdown sequence:
  1. Close Redis connection pool.
  2. Dispose SQLAlchemy engine (drains connection pool).

The app does NOT run database initializations on startup.  Migrations are a
deployment step, not a runtime step.  Run `python scripts/init_db.py` separately.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.connection import init_db_pool, close_db_pool
from app.core.redis_client import close_redis
from app.api.documents import router as documents_router
from app.api.analysis import router as analysis_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    # -- Startup --
    settings = get_settings()

    # Validate n == b * r (raises immediately if misconfigured)
    # get_settings() already called the validator, but call again here
    # so the error appears in server logs at startup rather than silently.
    assert settings.MINHASH_N == settings.LSH_B * settings.LSH_R, (
        f"Config error: MINHASH_N={settings.MINHASH_N} != "
        f"LSH_B*LSH_R={settings.LSH_B * settings.LSH_R}"
    )

    # Initialize benchmark_stats storage on app state
    app.state.benchmark_stats = {}

    await init_db_pool()

    yield  # application runs here

    # -- Shutdown --
    await close_redis()
    await close_db_pool()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Document Similarity System",
        description=(
            "MinHash + LSH plagiarism detection with dual Postgres/Redis backends. "
            "Every algorithmic step is explainable and benchmarkable."
        ),
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS — allow the Vite dev server and any localhost origin during development
    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    if settings.APP_ENV != "production":
        # In development, also allow all localhost ports
        origins.append("http://localhost")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount routers
    app.include_router(documents_router)
    app.include_router(analysis_router)

    @app.get("/health", tags=["meta"])
    async def health():
        """Simple liveness check."""
        return {"status": "ok", "version": "0.1.0"}

    return app


app = create_app()
