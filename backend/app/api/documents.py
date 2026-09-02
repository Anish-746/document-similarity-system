import time
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
import asyncpg

from app.core.config import get_settings
from app.core.exceptions import DuplicateDocumentError
from app.core.redis_client import get_redis
from app.db.connection import get_db_connection
from app.db import queries
from app.services.similarity_service import ingest_document, remove_document_from_redis
from app.services.redis_lsh_store import RedisLSHStore
from app.api.schemas import DocumentResponse, DocumentListResponse, ErrorResponse

router = APIRouter(prefix="/documents", tags=["documents"])

_CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".c", ".cpp",
    ".h", ".cs", ".rb", ".rs", ".swift", ".kt", ".php", ".sh", ".bash",
}

def _detect_mode(filename: str) -> str:
    from pathlib import Path
    return "code" if Path(filename).suffix.lower() in _CODE_EXTENSIONS else "text"


@router.post(
    "/upload",
    response_model=list[DocumentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Upload one or more text/code files",
    responses={
        409: {"model": ErrorResponse, "description": "Duplicate content"},
        400: {"model": ErrorResponse, "description": "Empty or unreadable file"},
    },
)
async def upload_documents(
    files: list[UploadFile],
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    created_docs = []

    for upload in files:
        raw = await upload.read()
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File '{upload.filename}' is not valid UTF-8 text.",
            )

        mode = _detect_mode(upload.filename or "unknown.txt")

        try:
            doc = await ingest_document(
                conn=conn,
                filename=upload.filename or "unknown.txt",
                content=content,
                mode=mode,
            )
        except DuplicateDocumentError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )

        created_docs.append(doc)

    responses = []
    for doc in created_docs:
        responses.append(DocumentResponse.model_validate(doc))

    return responses


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List all documents with metadata",
)
async def list_documents(
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    docs = await queries.list_documents(conn)
    responses = [DocumentResponse.model_validate(d) for d in docs]
    return DocumentListResponse(documents=responses, total=len(responses))


@router.get(
    "/{doc_id}",
    response_model=DocumentResponse,
    summary="Get a single document by ID",
    responses={404: {"model": ErrorResponse}},
)
async def get_document(
    doc_id: int,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    doc = await queries.get_document(conn, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found.")
    return DocumentResponse.model_validate(doc)


@router.delete(
    "/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document from all stores",
    responses={404: {"model": ErrorResponse}},
)
async def delete_document(
    doc_id: int,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    doc = await queries.get_document(conn, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found.")

    settings = get_settings()
    redis_store = RedisLSHStore(redis=get_redis(), lsh_b=settings.LSH_B)

    await remove_document_from_redis(conn=conn, redis_store=redis_store, doc_id=doc_id)
    await queries.delete_document(conn, doc_id)
