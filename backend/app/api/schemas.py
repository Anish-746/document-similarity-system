"""
schemas.py -- Pydantic response/request models for all API endpoints.

Keeping schemas in one file makes it easy to see the full API contract
without jumping between router files.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Document schemas
# ---------------------------------------------------------------------------

class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    content_hash: str
    mode: str
    is_indexed: bool
    uploaded_at: datetime
    num_shingles: Optional[int] = None   # joined from minhash_signatures


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int


# ---------------------------------------------------------------------------
# Analysis schemas
# ---------------------------------------------------------------------------

class AnalysisRunResponse(BaseModel):
    method: str
    processed: int
    pairs_found: int
    pairs_flagged: int
    duration_seconds: float


class RebuildIndexResponse(BaseModel):
    reindexed: int
    duration_seconds: float


class SimilarityPairResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_a_id: int
    document_b_id: int
    document_a_filename: Optional[str] = None
    document_b_filename: Optional[str] = None
    estimated_similarity: float
    exact_similarity: float
    is_flagged: bool
    computed_at: datetime


class PairsListResponse(BaseModel):
    pairs: list[SimilarityPairResponse]
    total: int
    page: int
    page_size: int


class BenchmarkStats(BaseModel):
    naive_duration_seconds: Optional[float] = None
    lsh_duration_seconds: Optional[float] = None
    speedup_multiplier: Optional[float] = None


class StatsResponse(BaseModel):
    total_documents: int
    indexed_documents: int
    total_pairs_computed: int
    flagged_pairs: int
    # LSH efficiency
    total_possible_pairs: int        # N choose 2
    actual_pairs_compared: int       # = total_pairs_computed (via LSH candidates)
    comparison_reduction_pct: float  # (1 - actual/possible) * 100
    # Benchmark (populated by /analysis/run calls)
    benchmark: BenchmarkStats


# ---------------------------------------------------------------------------
# Pair detail schema (for side-by-side view with shared shingles)
# ---------------------------------------------------------------------------

class PairDetailResponse(BaseModel):
    pair: SimilarityPairResponse
    content_a: str
    content_b: str
    shared_shingles: list[str]


# ---------------------------------------------------------------------------
# Error schema
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    detail: str
