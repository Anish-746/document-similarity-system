"""
redis_lsh_store.py -- Redis-backed LSH index store.

DATA MODEL:
  Key:   lsh:band:{band_index}:hash:{bucket_hash}
  Type:  Redis Set
  Value: Set of document_id strings (e.g. {"1", "42", "99"})

  Example (band 3, bucket hash "a1b2c3d4e5f6a7b8", documents 1 and 42):
    SADD lsh:band:3:hash:a1b2c3d4e5f6a7b8 "1" "42"

WHY REDIS SETS ARE OPTIMAL FOR THIS WORKLOAD:
  The LSH candidate lookup is semantically "give me the UNION of sets":
    C = UNION over each band i of { doc_ids in bucket (i, b_hashes[i]) }

  Redis Set operations:
    SADD   O(1) per member             -- fast inserts during indexing
    SREM   O(1) per member             -- fast deletes on document removal
    SMEMBERS O(|S|)                    -- return all members in one RTT
    SUNION O(sum(|S_i|))               -- union across all bands in one RTT

  Everything lives in RAM with O(1) hash-table lookups.  No disk I/O,
  no B-tree traversal, no buffer pool — just pointer chasing in memory.

  Benchmark expectation: 10-100x faster than Postgres for candidate lookup
  at typical corpus sizes (500-10,000 documents).

DELETION STRATEGY (see implementation_plan.md Q2):
  We re-derive the band hashes from the document's stored MinHash signature
  in Postgres rather than storing a reverse index in Redis.  This keeps
  Redis state minimal and avoids a second source of truth.  At deletion time,
  we read the signature from Postgres (one query) and issue b SREM commands.

KEY LIFETIME:
  Redis keys are not given a TTL.  They persist until:
    a) flush_index() is called (FLUSHDB or scan-and-delete lsh:* keys), or
    b) the Redis container is restarted (persistence is disabled by design).
  Both cases are documented in the redis_client.py module.
"""

from redis.asyncio import Redis

from app.core.config import get_settings


_KEY_PREFIX = "lsh"


def _band_key(band_index: int, bucket_hash: str) -> str:
    """Construct the Redis key for a given (band_index, bucket_hash) pair.

    Format: lsh:band:{band_index}:hash:{bucket_hash}

    We include 'band' and 'hash' as literal separators so the key is
    human-readable in redis-cli and the pattern lsh:* captures all LSH keys.
    """
    return f"{_KEY_PREFIX}:band:{band_index}:hash:{bucket_hash}"


class RedisLSHStore:
    """Redis implementation of the LSHStore protocol.

    Args:
        redis:  An async Redis client (from redis_client.get_redis()).
        lsh_b:  Number of bands (from settings).
    """

    def __init__(self, redis: Redis, lsh_b: int) -> None:
        self._redis = redis
        self._lsh_b = lsh_b

    async def add_document(self, doc_id: int, b_hashes: list[str]) -> None:
        """Add a document to all b band buckets using a Redis pipeline.

        We use a pipeline (fire-and-forget batch) to send all b SADD commands
        in a single network round-trip rather than b separate round-trips.

        Args:
            doc_id:   Document primary key (stored as string in the Redis set).
            b_hashes: List of b bucket-hash strings.
        """
        doc_id_str = str(doc_id)
        # Pipeline batches commands and executes them atomically from the
        # server's perspective (not a transaction, but one round-trip).
        async with self._redis.pipeline(transaction=False) as pipe:
            for band_index, bucket_hash in enumerate(b_hashes):
                key = _band_key(band_index, bucket_hash)
                pipe.sadd(key, doc_id_str)
            await pipe.execute()

    async def get_candidates(self, b_hashes: list[str]) -> set[int]:
        """Return all document IDs sharing at least one band bucket.

        Strategy:
          1. Build the b Redis keys for the query document's band hashes.
          2. Use SUNION to get the union of all matching sets in one command.
             Redis executes SUNION server-side, returning just the union.
          3. Convert the result strings to ints.

        This is O(sum(|bucket_sizes|)) in Redis time, which is effectively
        O(candidates) — an extremely tight operation.

        Args:
            b_hashes: Band hashes of the query document.

        Returns:
            set[int] of candidate document IDs.
        """
        keys = [_band_key(i, h) for i, h in enumerate(b_hashes)]

        # SUNION returns the union of all specified set keys.
        # Keys that don't exist are treated as empty sets (no error).
        members: set[str] = await self._redis.sunion(*keys)

        return {int(m) for m in members}

    async def remove_document(self, doc_id: int, b_hashes: list[str]) -> None:
        """Remove a document from all its band buckets.

        We re-derive the band keys from the b_hashes (which the caller
        computes from the stored signature in Postgres — see deletion strategy
        note in the module docstring).

        Args:
            doc_id:   Primary key of the document being removed.
            b_hashes: The document's band hashes (re-derived from its signature).
        """
        doc_id_str = str(doc_id)
        async with self._redis.pipeline(transaction=False) as pipe:
            for band_index, bucket_hash in enumerate(b_hashes):
                key = _band_key(band_index, bucket_hash)
                pipe.srem(key, doc_id_str)
            await pipe.execute()

    async def flush_index(self) -> None:
        """Delete all LSH index keys from Redis.

        We scan for keys matching 'lsh:*' and delete them in batches of 1000.
        This is safer than FLUSHDB (which would wipe all Redis data, including
        any non-LSH keys if this Redis instance is shared).

        For a dedicated LSH Redis instance FLUSHDB would be equivalent and
        slightly faster, but scan-and-delete is universally safe.
        """
        cursor = 0
        pattern = f"{_KEY_PREFIX}:*"
        batch_size = 1000

        while True:
            cursor, keys = await self._redis.scan(
                cursor=cursor, match=pattern, count=batch_size
            )
            if keys:
                await self._redis.delete(*keys)
            if cursor == 0:
                break
