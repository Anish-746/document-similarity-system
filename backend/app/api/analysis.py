import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
import asyncpg

from app.db.connection import get_db_connection
from app.db import queries
from app.core.redis_client import get_redis
from app.core.config import get_settings
from app.services.redis_lsh_store import RedisLSHStore
from app.services.similarity_service import (
    run_analysis,
    rebuild_index,
    get_shared_shingles,
)
from app.api.schemas import (
    AnalysisRunResponse,
    RebuildIndexResponse,
    SimilarityPairResponse,
    PairsListResponse,
    PairDetailResponse,
    StatsResponse,
    BenchmarkStats,
    ErrorResponse,
)

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post(
    "/run",
    response_model=AnalysisRunResponse,
    summary="Run LSH analysis on un-indexed documents",
)
async def run_analysis_endpoint(
    request: Request,
    method: Literal["lsh", "naive"] = Query(
        default="lsh",
        description="Candidate lookup method. 'lsh' uses Redis buckets (O(N)), 'naive' compares all pairs (O(N^2)).",
    ),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    settings = get_settings()

    store = RedisLSHStore(redis=get_redis(), lsh_b=settings.LSH_B)

    t0 = time.perf_counter()
    result = await run_analysis(conn=conn, store=store, method=method)
    duration = time.perf_counter() - t0

    if not hasattr(request.app.state, "benchmark_stats"):
        request.app.state.benchmark_stats = {}
    request.app.state.benchmark_stats[method] = duration

    return AnalysisRunResponse(
        method=method,
        processed=result["processed"],
        pairs_found=result["pairs_found"],
        pairs_flagged=result["pairs_flagged"],
        duration_seconds=round(duration, 4),
    )


@router.post(
    "/rebuild-index",
    response_model=RebuildIndexResponse,
    summary="Flush the LSH index and rebuild from stored signatures",
)
async def rebuild_index_endpoint(
    request: Request,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    settings = get_settings()
    redis_store = RedisLSHStore(redis=get_redis(), lsh_b=settings.LSH_B)

    t0 = time.perf_counter()
    result = await rebuild_index(conn=conn, redis_store=redis_store)
    duration = time.perf_counter() - t0

    return RebuildIndexResponse(
        reindexed=result["reindexed"],
        duration_seconds=round(duration, 4),
    )


@router.get(
    "/pairs",
    response_model=PairsListResponse,
    summary="List computed similarity pairs (paginated, filterable)",
)
async def list_pairs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    min_similarity: float = Query(default=0.0, ge=0.0, le=1.0),
    flagged_only: bool = Query(default=False),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    offset = (page - 1) * page_size
    
    pairs_dicts, total = await queries.list_similarity_pairs(
        conn=conn,
        min_sim=min_similarity,
        flagged_only=flagged_only,
        limit=page_size,
        offset=offset
    )

    pairs = []
    for d in pairs_dicts:
        p = SimilarityPairResponse.model_validate(d)
        p.document_a_filename = d["document_a_filename"]
        p.document_b_filename = d["document_b_filename"]
        pairs.append(p)

    return PairsListResponse(
        pairs=pairs,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/pairs/{pair_id}",
    response_model=PairDetailResponse,
    summary="Get pair detail with shared shingles for highlighting",
    responses={404: {"model": ErrorResponse}},
)
async def get_pair_detail(
    pair_id: int,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    pair_dict = await queries.get_pair(conn, pair_id)
    if not pair_dict:
        raise HTTPException(status_code=404, detail=f"Pair {pair_id} not found.")

    doc_a = await queries.get_document(conn, pair_dict["document_a_id"])
    doc_b = await queries.get_document(conn, pair_dict["document_b_id"])

    if not doc_a or not doc_b:
        raise HTTPException(
            status_code=404,
            detail="One or both documents in this pair have been deleted.",
        )

    shared = await get_shared_shingles(conn, pair_dict["document_a_id"], pair_dict["document_b_id"])

    p_response = SimilarityPairResponse.model_validate(pair_dict)
    p_response.document_a_filename = doc_a["filename"]
    p_response.document_b_filename = doc_b["filename"]

    return PairDetailResponse(
        pair=p_response,
        content_a=doc_a["content"],
        content_b=doc_b["content"],
        shared_shingles=shared,
    )


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Return corpus stats and benchmark timings",
)
async def get_stats(
    request: Request,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    stats = await queries.get_stats(conn)
    total_docs = stats["total_documents"]
    indexed_docs = stats["indexed_documents"]
    total_pairs = stats["total_pairs"]
    flagged_pairs = stats["flagged_pairs"]

    n = total_docs
    possible_pairs = n * (n - 1) // 2 if n >= 2 else 0

    actual = total_pairs
    reduction_pct = (
        round((1 - actual / possible_pairs) * 100, 2)
        if possible_pairs > 0
        else 0.0
    )

    bm_raw: dict = getattr(request.app.state, "benchmark_stats", {})
    naive_time = bm_raw.get("naive")
    lsh_time = bm_raw.get("lsh")
    speedup = round(naive_time / lsh_time, 2) if (naive_time and lsh_time and lsh_time > 0) else None

    return StatsResponse(
        total_documents=total_docs,
        indexed_documents=indexed_docs,
        total_pairs_computed=total_pairs,
        flagged_pairs=flagged_pairs,
        total_possible_pairs=possible_pairs,
        actual_pairs_compared=actual,
        comparison_reduction_pct=reduction_pct,
        benchmark=BenchmarkStats(
            naive_duration_seconds=round(naive_time, 4) if naive_time else None,
            lsh_duration_seconds=round(lsh_time, 4) if lsh_time else None,
            speedup_multiplier=speedup,
        ),
    )
