"""
redis_client.py -- Async Redis connection singleton.

WHY REDIS FOR THE LSH INDEX?
  The LSH index lookup is a pure set-membership query:
    "Which documents share this band bucket with the new document?"

  Redis Sets offer:
    - SADD / SREM: O(1) per member
    - SMEMBERS: O(|S|) — returns all members in one round trip
    - SUNIONSTORE / SUNION across multiple keys: O(sum(|S_i|))

  A Postgres table with indexes supports the same query but incurs:
    - Buffer pool misses → random disk I/O
    - Row tuple overhead (~23 bytes header + data per row)
    - Planner overhead for each query

  For candidate lookup (the hot path during analysis), Redis is expected
  to be 10-100x faster than Postgres.  This is what the benchmark measures.

KEY SCHEMA (read-only documentation here; implemented in RedisLSHStore):
  lsh:band:{band_index}:hash:{bucket_hash}  → Redis Set of document_id strings

  Example:
    SADD lsh:band:3:hash:a1b2c3d4e5f6a7b8  "42"
    SMEMBERS lsh:band:3:hash:a1b2c3d4e5f6a7b8  ->  {"42", "17", "91"}

LIFECYCLE:
  The Redis LSH index is ephemeral by design (we disable RDB/AOF persistence
  in docker-compose.yml).  It is rebuilt from the minhash_signatures Postgres
  table whenever LSH parameters (b, r) change — see POST /analysis/rebuild-index.
  This is intentional cache invalidation, not a bug.
"""

from redis.asyncio import Redis, from_url

from app.core.config import get_settings

_redis_client: Redis | None = None


def get_redis() -> Redis:
    """Return the module-level Redis async client singleton.

    The client is created lazily on first call and reused thereafter.
    redis.asyncio.Redis manages its own internal connection pool; we do
    not need to create separate pools manually.

    Note: This is NOT an async function because Redis.from_url() is
    synchronous (it only creates the pool descriptor, not actual sockets).
    The actual TCP connections are established lazily on the first command.
    """
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,  # keys and values come back as str, not bytes
        )
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection pool.  Call this in the app shutdown hook."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
