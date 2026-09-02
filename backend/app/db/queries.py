import asyncpg
from typing import Optional, List, Dict, Any, Tuple

# -- Documents --

async def get_document_by_hash(conn: asyncpg.Connection, content_hash: str) -> Optional[dict]:
    row = await conn.fetchrow(
        "SELECT id FROM documents WHERE content_hash = $1",
        content_hash
    )
    return dict(row) if row else None

async def insert_document(conn: asyncpg.Connection, filename: str, content: str, content_hash: str, mode: str) -> int:
    row = await conn.fetchrow(
        """
        INSERT INTO documents (filename, content, content_hash, mode)
        VALUES ($1, $2, $3, $4)
        RETURNING id
        """,
        filename, content, content_hash, mode
    )
    return row["id"]

async def list_documents(conn: asyncpg.Connection) -> List[dict]:
    # We also need the num_shingles from signatures
    rows = await conn.fetch(
        """
        SELECT d.*, s.num_shingles 
        FROM documents d
        LEFT JOIN minhash_signatures s ON d.id = s.document_id
        ORDER BY d.uploaded_at DESC
        """
    )
    return [dict(r) for r in rows]

async def get_document(conn: asyncpg.Connection, doc_id: int) -> Optional[dict]:
    row = await conn.fetchrow(
        """
        SELECT d.*, s.num_shingles 
        FROM documents d
        LEFT JOIN minhash_signatures s ON d.id = s.document_id
        WHERE d.id = $1
        """,
        doc_id
    )
    return dict(row) if row else None

async def delete_document(conn: asyncpg.Connection, doc_id: int) -> None:
    await conn.execute("DELETE FROM documents WHERE id = $1", doc_id)

async def get_unindexed_documents(conn: asyncpg.Connection, doc_ids: Optional[List[int]] = None) -> List[dict]:
    if doc_ids:
        rows = await conn.fetch(
            "SELECT * FROM documents WHERE is_indexed = false AND id = ANY($1)",
            doc_ids
        )
    else:
        rows = await conn.fetch("SELECT * FROM documents WHERE is_indexed = false")
    return [dict(r) for r in rows]

async def get_all_documents(conn: asyncpg.Connection) -> List[dict]:
    rows = await conn.fetch("SELECT * FROM documents")
    return [dict(r) for r in rows]

async def mark_document_indexed(conn: asyncpg.Connection, doc_id: int) -> None:
    await conn.execute("UPDATE documents SET is_indexed = true WHERE id = $1", doc_id)

async def reset_indexed_status(conn: asyncpg.Connection) -> None:
    await conn.execute("UPDATE documents SET is_indexed = false")

async def mark_all_indexed(conn: asyncpg.Connection) -> None:
    await conn.execute("UPDATE documents SET is_indexed = true")

# -- Signatures --

async def insert_signature(conn: asyncpg.Connection, document_id: int, signature: List[int], num_shingles: int) -> None:
    await conn.execute(
        """
        INSERT INTO minhash_signatures (document_id, signature, num_shingles)
        VALUES ($1, $2, $3)
        """,
        document_id, signature, num_shingles
    )

async def get_signature(conn: asyncpg.Connection, document_id: int) -> Optional[dict]:
    row = await conn.fetchrow(
        "SELECT * FROM minhash_signatures WHERE document_id = $1",
        document_id
    )
    return dict(row) if row else None

async def get_all_signatures(conn: asyncpg.Connection) -> List[dict]:
    rows = await conn.fetch("SELECT * FROM minhash_signatures")
    return [dict(r) for r in rows]

# -- Similarity Pairs --

async def insert_similarity_pair(conn: asyncpg.Connection, doc_a_id: int, doc_b_id: int, est_sim: float, exact_sim: float, is_flagged: bool) -> None:
    await conn.execute(
        """
        INSERT INTO similarity_pairs (document_a_id, document_b_id, estimated_similarity, exact_similarity, is_flagged, computed_at)
        VALUES ($1, $2, $3, $4, $5, NOW())
        ON CONFLICT (document_a_id, document_b_id) DO UPDATE SET
            estimated_similarity = EXCLUDED.estimated_similarity,
            exact_similarity = EXCLUDED.exact_similarity,
            is_flagged = EXCLUDED.is_flagged,
            computed_at = EXCLUDED.computed_at
        """,
        doc_a_id, doc_b_id, est_sim, exact_sim, is_flagged
    )

async def list_similarity_pairs(conn: asyncpg.Connection, min_sim: float, flagged_only: bool, limit: int, offset: int) -> Tuple[List[dict], int]:
    conds = ["exact_similarity >= $1"]
    args = [min_sim]
    
    if flagged_only:
        conds.append("is_flagged = true")
        
    where_clause = " AND ".join(conds)
    
    count_query = f"SELECT COUNT(*) FROM similarity_pairs WHERE {where_clause}"
    total = await conn.fetchval(count_query, *args)
    
    # We also want to fetch the filenames
    data_query = f"""
        SELECT p.*, da.filename AS document_a_filename, db.filename AS document_b_filename
        FROM similarity_pairs p
        JOIN documents da ON p.document_a_id = da.id
        JOIN documents db ON p.document_b_id = db.id
        WHERE {where_clause}
        ORDER BY exact_similarity DESC
        LIMIT ${len(args) + 1} OFFSET ${len(args) + 2}
    """
    rows = await conn.fetch(data_query, *args, limit, offset)
    return [dict(r) for r in rows], total

async def get_pair(conn: asyncpg.Connection, pair_id: int) -> Optional[dict]:
    row = await conn.fetchrow(
        """
        SELECT p.*, da.filename AS document_a_filename, db.filename AS document_b_filename
        FROM similarity_pairs p
        JOIN documents da ON p.document_a_id = da.id
        JOIN documents db ON p.document_b_id = db.id
        WHERE p.id = $1
        """,
        pair_id
    )
    return dict(row) if row else None

# -- Stats --

async def get_stats(conn: asyncpg.Connection) -> dict:
    total_docs = await conn.fetchval("SELECT COUNT(*) FROM documents")
    indexed_docs = await conn.fetchval("SELECT COUNT(*) FROM documents WHERE is_indexed = true")
    total_pairs = await conn.fetchval("SELECT COUNT(*) FROM similarity_pairs")
    flagged_pairs = await conn.fetchval("SELECT COUNT(*) FROM similarity_pairs WHERE is_flagged = true")
    
    return {
        "total_documents": total_docs,
        "indexed_documents": indexed_docs,
        "total_pairs": total_pairs,
        "flagged_pairs": flagged_pairs
    }
