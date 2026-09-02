"""
lsh.py -- Locality-Sensitive Hashing banding for MinHash signatures.

LSH BANDING THEORY:
===================

Given a MinHash signature of length n, split it into b bands of r rows each
(n = b * r).  Two documents become *candidates* if their signatures agree on
ALL r rows of at least ONE band.

Probability that document pair with Jaccard similarity s becomes a candidate:

  P(candidate | s) = 1 - (1 - s^r)^b

This is an S-shaped curve:
  - Below the threshold t = (1/b)^(1/r), most pairs are NOT candidates.
  - Above t, most pairs ARE candidates.

The "knee" of the S-curve is approximately at t = (1/b)^(1/r).
With b=20, r=5: t = (1/20)^(1/5) = 20^(-0.2) ~= 0.55

This means:
  - Pairs with Jaccard ~= 0.3 are candidates with probability ~= 1%  (rare)
  - Pairs with Jaccard ~= 0.7 are candidates with probability ~= 86% (common)
  - Pairs with Jaccard ~= 0.9 are candidates with probability ~= 99.97%

BANDING TRADEOFF:
  - More bands (larger b, smaller r) -> lower threshold, more candidates,
    higher recall but more false positives (more exact comparisons needed).
  - Fewer bands (smaller b, larger r) -> higher threshold, fewer candidates,
    fewer false positives but more false negatives (true duplicates missed).

BUCKET HASHING:
  Each band is a vector of r integers.  We hash this vector to a single
  compact string using SHA-1 of the byte representation.  This serves as
  the bucket key.  Two documents land in the same bucket (and become
  candidates) iff their band-hashes match.
"""

import hashlib
import numpy as np


def band_hashes(signature: np.ndarray, b: int, r: int) -> list[str]:
    """Split a MinHash signature into b bands and hash each band to a string.

    Args:
        signature: MinHash signature array of length n = b * r.
        b: Number of bands.
        r: Number of rows per band.

    Returns:
        List of b hex-digest strings, one per band.
        band_hashes[i] is the bucket key for band i.

    Raises:
        ValueError: If len(signature) != b * r.
    """
    n = len(signature)
    if n != b * r:
        raise ValueError(
            f"Signature length {n} must equal b*r = {b}*{r} = {b * r}"
        )

    hashes: list[str] = []
    for band_idx in range(b):
        start = band_idx * r
        end = start + r
        band_vector = signature[start:end]

        # Convert the band's integer array to a deterministic byte string.
        # Using '>u8' (big-endian uint64) ensures consistent byte layout.
        band_bytes = band_vector.astype(">u8").tobytes()

        # SHA-1 of the byte string is our bucket key.
        # Truncating to 16 hex chars (64 bits) keeps keys compact while
        # keeping collision probability negligible for typical corpus sizes.
        bucket_hash = hashlib.sha1(band_bytes).hexdigest()[:16]
        hashes.append(bucket_hash)

    return hashes
