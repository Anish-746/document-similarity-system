import hashlib
import numpy as np
from datetime import datetime
import asyncpg

from app.algorithms.shingling import normalize_text, shingle, exact_jaccard, shared_shingles
from app.algorithms.minhash import MinHash, estimated_jaccard
from app.algorithms.lsh import band_hashes
from app.core.config import get_settings
from app.core.exceptions import DuplicateDocumentError
from app.services.redis_lsh_store import RedisLSHStore
from app.db import queries


def _get_minhash() -> MinHash:
    """Singleton-style MinHash factory using settings."""
    s = get_settings()
    return MinHash(n=s.MINHASH_N, seed=42)

def _sig_to_db(sig: np.ndarray) -> list[int]:
    return [int(v % (2**31)) for v in sig.tolist()]

def _sig_from_db(db_sig: list[int]) -> np.ndarray:
    return np.array(db_sig, dtype=np.uint64)

def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

# ---------------------------------------------------------------------------
# Document ingestion
# ---------------------------------------------------------------------------

async def ingest_document(
    conn: asyncpg.Connection,
    filename: str,
    content: str,
    mode: str = "text",
) -> dict:
    if not content.strip():
        raise ValueError("Document content is empty.")

    c_hash = _content_hash(content)

    existing = await queries.get_document_by_hash(conn, c_hash)
    if existing:
        raise DuplicateDocumentError(f"Duplicate document: content_hash={c_hash} already exists.")

    settings = get_settings()
    normalized = normalize_text(content, mode=mode)
    shingles = shingle(normalized, k=settings.SHINGLE_K)
    mh = _get_minhash()
    sig = mh.sign(shingles)

    doc_id = await queries.insert_document(conn, filename, content, c_hash, mode)
    await queries.insert_signature(conn, doc_id, _sig_to_db(sig), len(shingles))

    return await queries.get_document(conn, doc_id)

# ---------------------------------------------------------------------------
# Analysis (candidate lookup + similarity scoring)
# ---------------------------------------------------------------------------

async def run_analysis(
    conn: asyncpg.Connection,
    store: RedisLSHStore,
    method: str = "lsh",
    doc_ids: list[int] | None = None,
) -> dict:
    settings = get_settings()

    docs = await queries.get_unindexed_documents(conn, doc_ids)
    if not docs:
        return {"processed": 0, "pairs_found": 0, "pairs_flagged": 0}

    # BATCH LOAD
    all_sigs = await queries.get_all_signatures(conn)
    sig_map = {row["document_id"]: row for row in all_sigs}

    all_docs = await queries.get_all_documents(conn)
    doc_map = {d["id"]: d for d in all_docs}

    _shingle_cache: dict[int, frozenset] = {}

    def _get_shingles(d: dict) -> frozenset:
        if d["id"] not in _shingle_cache:
            normalized = normalize_text(d["content"], mode=d["mode"])
            _shingle_cache[d["id"]] = shingle(normalized, k=settings.SHINGLE_K)
        return _shingle_cache[d["id"]]

    processed = 0
    pairs_found = 0
    pairs_flagged = 0

    for doc in docs:
        sig_row = sig_map.get(doc["id"])
        if not sig_row:
            continue

        sig = _sig_from_db(sig_row["signature"])
        b_hashes = band_hashes(sig, b=settings.LSH_B, r=settings.LSH_R)

        if method == "naive":
            candidates = set(doc_map.keys())
        else:
            candidates = await store.get_candidates(b_hashes)
        candidates.discard(doc["id"])

        shingles_a = _get_shingles(doc)

        for cand_id in candidates:
            cand_sig_row = sig_map.get(cand_id)
            if not cand_sig_row:
                continue

            cand_sig = _sig_from_db(cand_sig_row["signature"])
            est_j = estimated_jaccard(sig, cand_sig)

            cand_doc = doc_map.get(cand_id)
            if not cand_doc:
                continue

            shingles_b = _get_shingles(cand_doc)
            exact_j = exact_jaccard(shingles_a, shingles_b)
            flagged = exact_j >= settings.SIMILARITY_THRESHOLD

            id_a, id_b = min(doc["id"], cand_id), max(doc["id"], cand_id)

            await queries.insert_similarity_pair(conn, id_a, id_b, est_j, exact_j, flagged)
            
            pairs_found += 1
            if flagged:
                pairs_flagged += 1

        await store.add_document(doc["id"], b_hashes)
        await queries.mark_document_indexed(conn, doc["id"])
        processed += 1

    return {
        "processed": processed,
        "pairs_found": pairs_found,
        "pairs_flagged": pairs_flagged,
    }

# ---------------------------------------------------------------------------
# Index rebuild
# ---------------------------------------------------------------------------

async def rebuild_index(
    conn: asyncpg.Connection,
    redis_store: RedisLSHStore,
) -> dict:
    settings = get_settings()

    await redis_store.flush_index()
    await queries.reset_indexed_status(conn)

    sig_rows = await queries.get_all_signatures(conn)

    reindexed = 0
    for sig_row in sig_rows:
        sig = _sig_from_db(sig_row["signature"])
        b_hashes = band_hashes(sig, b=settings.LSH_B, r=settings.LSH_R)

        await redis_store.add_document(sig_row["document_id"], b_hashes)
        reindexed += 1

    await queries.mark_all_indexed(conn)

    return {"reindexed": reindexed}

# ---------------------------------------------------------------------------
# Document deletion (Redis SREM)
# ---------------------------------------------------------------------------

async def remove_document_from_redis(
    conn: asyncpg.Connection,
    redis_store: RedisLSHStore,
    doc_id: int,
) -> None:
    settings = get_settings()
    sig_row = await queries.get_signature(conn, doc_id)
    if not sig_row:
        return

    sig = _sig_from_db(sig_row["signature"])
    b_hashes = band_hashes(sig, b=settings.LSH_B, r=settings.LSH_R)
    await redis_store.remove_document(doc_id, b_hashes)

# ---------------------------------------------------------------------------
# Shared shingles helper (for Pair Detail view)
# ---------------------------------------------------------------------------

async def get_shared_shingles(
    conn: asyncpg.Connection,
    doc_a_id: int,
    doc_b_id: int,
) -> list[str]:
    settings = get_settings()
    doc_a = await queries.get_document(conn, doc_a_id)
    doc_b = await queries.get_document(conn, doc_b_id)
    if not doc_a or not doc_b:
        return []

    sa = shingle(normalize_text(doc_a["content"], mode=doc_a["mode"]), k=settings.SHINGLE_K)
    sb = shingle(normalize_text(doc_b["content"], mode=doc_b["mode"]), k=settings.SHINGLE_K)
    return sorted(shared_shingles(sa, sb))
