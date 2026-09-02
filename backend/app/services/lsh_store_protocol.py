"""
lsh_store_protocol.py -- Shared interface (Protocol) for the RedisLSHStore.

The API layer receives whichever store was selected and calls it through
this interface, never touching Postgres/Redis details directly.

WHY A PROTOCOL INSTEAD OF AN ABC?
  Python Protocols enable structural subtyping ("duck typing with IDE support").
  We don't inherit from LSHStore -- we just implement the same method signatures.
  This makes it trivial to add a third backend (e.g. DynamoDB) without touching
  the protocol or the existing implementations.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class LSHStore(Protocol):
    """Common interface for Postgres and Redis LSH index backends.

    Each method maps to one phase of the LSH lifecycle:

      add_document    -- index a new document's band hashes
      get_candidates  -- retrieve candidate doc IDs that share >= 1 band bucket
      remove_document -- purge all index entries for a deleted document
      flush_index     -- wipe the entire index (called before rebuild)
    """

    async def add_document(self, doc_id: int, b_hashes: list[str]) -> None:
        """Add a document's band hashes to the index.

        Args:
            doc_id:   The document's primary key in the documents table.
            b_hashes: List of b bucket-hash strings from lsh.band_hashes().
                      len(b_hashes) must equal LSH_B.
        """
        ...

    async def get_candidates(self, b_hashes: list[str]) -> set[int]:
        """Return the set of document IDs that share at least one band bucket
        with the query document (represented by its band hashes).

        Args:
            b_hashes: Band hashes of the query document.

        Returns:
            set[int] of candidate document IDs (excluding the query itself).
        """
        ...

    async def remove_document(self, doc_id: int) -> None:
        """Remove all index entries for a deleted document.

        Args:
            doc_id: The primary key of the document being deleted.
        """
        ...

    async def flush_index(self) -> None:
        """Wipe the entire LSH index.

        Called by POST /analysis/rebuild-index before re-indexing all
        documents from scratch.  Should be fast (TRUNCATE / FLUSHDB-style).
        """
        ...
