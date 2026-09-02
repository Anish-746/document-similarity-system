"""
benchmark.py -- see docstring below.
"""
import os
os.environ["APP_ENV"] = "production"

import logging
logging.getLogger("asyncio").setLevel(logging.WARNING)

"""
benchmark.py -- LSH performance benchmark.

WHAT THIS MEASURES:
  The hot path in LSH-based similarity detection is candidate lookup:
  "Which documents share at least one band bucket with document X?"

  This script measures how long that operation takes across the full corpus
  using the RedisLSHStore (SUNION on in-memory Sets).

METHODOLOGY:
  1. Generate N_DOCS text documents (configurable; default 600).
     ~30% are near-duplicates of earlier documents (for realistic pairs).
  2. Ingest all documents (shingling + MinHash + signature storage).
  3. Run analysis/run with Redis -> time it.
  4. Print a results table.

CALLING CONVENTION:
  Run from the backend/ directory with the venv active:
    python scripts/benchmark.py [--docs 600] [--k 5] [--verbose]

  Requires the containers to be running:
    make services-up
    make init-db
"""

import argparse
import asyncio
import random
import sys
import time
from pathlib import Path

# Make sure the backend/ package is importable when running as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import get_settings
from app.db.connection import init_db_pool, close_db_pool, get_db_connection
from app.core.redis_client import get_redis, close_redis
from app.services.redis_lsh_store import RedisLSHStore
from app.services.similarity_service import (
    ingest_document,
    run_analysis,
    rebuild_index,
    _sig_from_db,
)
from app.algorithms.lsh import band_hashes
from app.db import queries


# ---------------------------------------------------------------------------
# Document generation
# ---------------------------------------------------------------------------

WORD_POOL = [
    "algorithm", "computer", "network", "database", "vector", "matrix",
    "function", "module", "server", "client", "protocol", "memory",
    "cache", "index", "query", "latency", "throughput", "pipeline",
    "cluster", "shard", "replica", "leader", "follower", "consensus",
    "hashing", "signature", "similarity", "jaccard", "minhash", "shingle",
    "candidate", "bucket", "band", "threshold", "precision", "recall",
    "random", "permutation", "universal", "prime", "modular", "collision",
]


def _random_sentence(n_words: int = 12, rng: random.Random = random) -> str:
    return " ".join(rng.choice(WORD_POOL) for _ in range(n_words))


def _random_paragraph(n_sentences: int = 6, rng: random.Random = random) -> str:
    return ". ".join(_random_sentence(rng=rng) for _ in range(n_sentences)) + "."


def generate_document(doc_index: int, rng: random.Random) -> tuple[str, str]:
    paragraphs = [_random_paragraph(rng=rng) for _ in range(4)]
    content = "\n\n".join(paragraphs)
    filename = f"doc_{doc_index:04d}.txt"
    return filename, content


def generate_corpus(
    n_docs: int,
    dup_ratio: float = 0.30,
    seed: int = 2025,
) -> list[tuple[str, str]]:
    rng = random.Random(seed)
    docs: list[tuple[str, str]] = []
    base_docs: list[str] = []

    for i in range(n_docs):
        if base_docs and rng.random() < dup_ratio:
            base = rng.choice(base_docs)
            words = base.split()
            n_replace = max(1, int(len(words) * 0.20))
            indices = rng.sample(range(len(words)), n_replace)
            for idx in indices:
                words[idx] = rng.choice(WORD_POOL)
            content = " ".join(words)
        else:
            _, content = generate_document(i, rng)
            base_docs.append(content)

        docs.append((f"doc_{i:04d}.txt", content))

    return docs


# ---------------------------------------------------------------------------
# Benchmark helpers
# ---------------------------------------------------------------------------

async def clear_all_data(conn) -> None:
    await conn.execute("TRUNCATE TABLE documents RESTART IDENTITY CASCADE")
    redis = get_redis()
    redis_store = RedisLSHStore(redis=redis, lsh_b=get_settings().LSH_B)
    await redis_store.flush_index()
    print("  Database and Redis cleared.")


async def ingest_corpus(
    conn,
    docs: list[tuple[str, str]],
    verbose: bool = False,
) -> int:
    ingested = 0
    skipped = 0
    n = len(docs)
    t0 = time.perf_counter()

    for i, (filename, content) in enumerate(docs):
        try:
            await ingest_document(conn=conn, filename=filename, content=content, mode="text")
            ingested += 1
        except ValueError:
            skipped += 1

        if verbose and (i + 1) % 50 == 0:
            elapsed = time.perf_counter() - t0
            print(f"    Ingested {i + 1}/{n} docs in {elapsed:.1f}s ...")

    return ingested


# ---------------------------------------------------------------------------
# Main benchmark
# ---------------------------------------------------------------------------

async def run_benchmark(n_docs: int, verbose: bool) -> None:
    settings = get_settings()
    redis = get_redis()

    print(f"\n{'='*60}")
    print(f"  Document Similarity System — LSH Benchmark")
    print(f"{'='*60}")
    print(f"  Corpus size : {n_docs} documents")
    print(f"  Parameters  : n={settings.MINHASH_N}, b={settings.LSH_B}, r={settings.LSH_R}, k={settings.SHINGLE_K}")
    print(f"  Threshold   : {settings.SIMILARITY_THRESHOLD}")
    print(f"{'='*60}\n")

    await init_db_pool()
    # Need to acquire a connection manually since we don't have FastAPI DI here
    from app.db.connection import _pool
    async with _pool.acquire() as conn:
        async with conn.transaction():
            print("[ Step 0 ] Clearing previous benchmark data ...")
            await clear_all_data(conn)
            
            print(f"\n[ Step 1 ] Generating {n_docs} documents (30% near-duplicates) ...")
            docs = generate_corpus(n_docs=n_docs, dup_ratio=0.30)
            print(f"  Generated {len(docs)} documents.")

            print(f"\n[ Step 2 ] Ingesting all documents (shingling + MinHash) ...")
            t_ingest_start = time.perf_counter()
            ingested = await ingest_corpus(conn=conn, docs=docs, verbose=verbose)
            t_ingest = time.perf_counter() - t_ingest_start
            print(f"  Ingested {ingested} documents in {t_ingest:.2f}s "
                  f"({ingested / t_ingest:.0f} docs/sec).")

            print(f"\n[ Step 3 ] Flushing indexes and pairs for fresh run ...")
            redis_store = RedisLSHStore(redis=redis, lsh_b=settings.LSH_B)
            await redis_store.flush_index()
            await conn.execute("TRUNCATE TABLE similarity_pairs RESTART IDENTITY CASCADE")

            print(f"\n[ Step 4 ] Running analysis with engine=REDIS ...")
            await queries.reset_indexed_status(conn)
            t_redis_start = time.perf_counter()
            redis_result = await run_analysis(conn=conn, store=redis_store)
            t_redis = time.perf_counter() - t_redis_start

            print(f"  Processed : {redis_result['processed']} docs")
            print(f"  Pairs found: {redis_result['pairs_found']}  |  Flagged: {redis_result['pairs_flagged']}")
            print(f"  Duration  : {t_redis:.4f}s")

            print(f"\n[ Step 5 ] Micro-benchmark: candidate lookup only ...")
            
            sample_sigs = await conn.fetch("SELECT * FROM minhash_signatures LIMIT 20")
            
            if sample_sigs:
                N_LOOKUPS = 100
                sample_bh = [
                    band_hashes(_sig_from_db(s["signature"]), b=settings.LSH_B, r=settings.LSH_R)
                    for s in sample_sigs
                ]

                t0 = time.perf_counter()
                for _ in range(N_LOOKUPS):
                    for bh in sample_bh:
                        await redis_store.get_candidates(bh)
                t_redis_lookup = (time.perf_counter() - t0) / (N_LOOKUPS * len(sample_sigs))

                print(f"  Per-lookup avg  ({N_LOOKUPS}x{len(sample_sigs)} samples):")
                print(f"    Redis:    {t_redis_lookup*1000:.3f} ms")
            else:
                print("  (no signatures found for micro-benchmark)")

    n = ingested
    possible_pairs = n * (n - 1) // 2 if n >= 2 else 0
    actual_pairs = redis_result["pairs_found"]
    reduction = (1 - actual_pairs / possible_pairs) * 100 if possible_pairs > 0 else 0

    print(f"\n{'='*60}")
    print(f"  BENCHMARK RESULTS")
    print(f"{'='*60}")
    print(f"\n  Corpus: {ingested} documents")
    print(f"  Possible pairs (N choose 2): {possible_pairs:,}")
    print(f"  Actual pairs compared (via LSH): {actual_pairs:,}")
    print(f"  Comparison reduction: {reduction:.1f}%")
    print(f"\n  End-to-end analysis duration: {t_redis:.4f}s")
    print(f"\n{'='*60}\n")

    await close_redis()
    await close_db_pool()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Benchmark Redis LSH index performance."
    )
    parser.add_argument(
        "--docs", type=int, default=600,
        help="Number of documents to generate (default: 600)."
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print ingestion progress every 50 documents."
    )
    args = parser.parse_args()

    asyncio.run(run_benchmark(n_docs=args.docs, verbose=args.verbose))


if __name__ == "__main__":
    main()
