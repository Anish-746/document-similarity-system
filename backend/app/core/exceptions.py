class DuplicateDocumentError(Exception):
    """Raised when a document with the same content hash already exists."""
    pass
