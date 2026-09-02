"""
config.py -- Application settings via Pydantic Settings.

All values are read from environment variables (or a .env file).
See backend/.env.example for the full list with documentation.

VALIDATION INVARIANT:
  LSH_B * LSH_R must equal MINHASH_N.  If this is violated the banding
  arithmetic breaks silently, so we validate it at startup and raise a
  descriptive error before any database connection is attempted.
"""

from functools import lru_cache
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Database ---
    DATABASE_URL: str

    # --- Redis ---
    REDIS_URL: str

    # --- Algorithm parameters ---
    MINHASH_N: int = 100       # Total number of hash functions / signature length
    SHINGLE_K: int = 5         # Character k-shingle width
    LSH_B: int = 20            # Number of LSH bands
    LSH_R: int = 5             # Rows per band  (MINHASH_N must equal LSH_B * LSH_R)

    # --- Similarity ---
    SIMILARITY_THRESHOLD: float = 0.7  # Pairs >= this are flagged

    # --- App ---
    APP_ENV: str = "development"

    @model_validator(mode="after")
    def validate_lsh_dimensions(self) -> "Settings":
        """Enforce the invariant n = b * r at process start.

        LSH banding math requires the signature to be evenly divisible into
        bands.  A mismatch here would produce silently wrong signatures.
        We catch it immediately rather than letting it corrupt stored data.
        """
        if self.MINHASH_N != self.LSH_B * self.LSH_R:
            raise ValueError(
                f"LSH dimension mismatch: MINHASH_N={self.MINHASH_N} "
                f"but LSH_B * LSH_R = {self.LSH_B} * {self.LSH_R} = {self.LSH_B * self.LSH_R}. "
                "Update .env so that MINHASH_N == LSH_B * LSH_R."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings singleton.

    Using lru_cache means we parse .env exactly once per process.
    In tests, call get_settings.cache_clear() before patching env vars.
    """
    return Settings()
