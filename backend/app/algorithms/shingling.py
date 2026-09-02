"""
shingling.py — Document fingerprinting via character k-shingles.

WHY SHINGLES?
A k-shingle (or k-gram) is a contiguous substring of k characters.
Representing a document as the *set* of its k-shingles lets us compare
documents using set-similarity metrics (Jaccard). Two documents that share
many phrases share many shingles, making this a natural fingerprint for
near-duplicate detection.

CHOOSING k:
- k=5 (character-level) works well for typical text: the space of 5-char
  strings is large enough that random matches are rare, yet small enough
  to tolerate minor edits.
- For very short documents, consider k=2 or k=3.
- For code comparison you may want token-level shingles; here we keep
  character-level for simplicity and configure k=5 by default.
"""

import re


def normalize_text(text: str, mode: str = "text") -> str:
    """Normalize a document string before shingling.

    Args:
        text: Raw document content.
        mode: "text" for prose, "code" for source-code files.

    Returns:
        Normalized string ready for shingling.

    Normalization steps:
        text mode  -> lowercase, collapse whitespace.
        code mode  -> additionally strip single-line (//, #) and
                     block (/* ... */) comments, then normalize
                     string literals to the token STR so that
                     trivial string-renaming doesn't hide similarity.
    """
    # Lowercase first so that code-mode sentinel tokens survive unchanged.
    text = text.lower()

    if mode == "code":
        # Strip block comments (/* ... */) -- non-greedy, DOTALL so newlines match
        text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
        # Strip single-line // and # comments (already lowercased)
        text = re.sub(r"//[^\n]*", " ", text)
        text = re.sub(r"#[^\n]*", " ", text)
        # Normalize string literals to a sentinel token that is detectable
        # after normalization.  We use 'strlit' (all-lowercase) so that the
        # downstream .lower() call (already applied above) does not change it.
        text = re.sub(r'"[^"]*"', "strlit", text)
        text = re.sub(r"'[^']*'", "strlit", text)

    # Collapse all whitespace to a single space
    text = re.sub(r"\s+", " ", text).strip()
    return text


def shingle(text: str, k: int = 5) -> frozenset:
    """Produce the set of character k-shingles from a (pre-normalized) text.

    A shingle is simply a sliding window of width k over the character sequence.
    Using a frozenset (rather than a list) discards order and duplicates, which
    is what we want for set-similarity: we care *whether* a shingle appears, not
    how many times.

    Args:
        text: Pre-normalized document string.
        k: Shingle width in characters (default 5).

    Returns:
        frozenset of k-character strings.

    Example:
        shingle("abcde", k=3) -> frozenset({"abc", "bcd", "cde"})
    """
    if len(text) < k:
        # Document too short to produce any k-shingle; return the whole text
        # as a single degenerate shingle so it can still be compared.
        return frozenset([text]) if text else frozenset()

    return frozenset(text[i : i + k] for i in range(len(text) - k + 1))


def exact_jaccard(set_a: frozenset, set_b: frozenset) -> float:
    """Compute the exact Jaccard similarity between two shingle sets.

    Jaccard(A, B) = |A intersection B| / |A union B|

    This is the *ground truth* similarity used to validate MinHash estimates.
    It is O(|A| + |B|) because Python frozenset intersection/union use hash
    tables internally.

    Args:
        set_a: Shingle set of the first document.
        set_b: Shingle set of the second document.

    Returns:
        Float in [0, 1].  Returns 0.0 if both sets are empty.
    """
    if not set_a and not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union


def shared_shingles(set_a: frozenset, set_b: frozenset) -> frozenset:
    """Return the shingles that appear in both documents.

    Used by the frontend Pair Detail view to highlight matching passages.

    Args:
        set_a: Shingle set of document A.
        set_b: Shingle set of document B.

    Returns:
        frozenset of shared shingle strings.
    """
    return set_a & set_b
