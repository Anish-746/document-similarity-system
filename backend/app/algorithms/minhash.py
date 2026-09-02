"""
minhash.py -- MinHash signature generation.

THE CORE PROBABILISTIC INSIGHT (why MinHash approximates Jaccard):
====================================================================

Let A and B be two shingle sets, and let h be a hash function that maps
shingles to integers and imposes a uniformly random ordering on the shingle
universe.

Define h_min(S) = min_{s in S} h(s) -- the minimum hash value in the set.

Now consider Pr[ h_min(A) == h_min(B) ]:

  The minimum over the *union* A union B lands on some element x.
  That element x is the minimum of A iff x is in A (and is also the
  overall minimum), which happens with probability |A| / |A union B|.
  By symmetry it is the minimum of B with probability |B| / |A union B|.

  For h_min(A) == h_min(B), the single minimum element over the union
  must be shared by *both* sets, i.e., it must lie in A intersection B.

  Therefore:
    Pr[ h_min(A) == h_min(B) ]
      = |A intersection B| / |A union B|
      = Jaccard(A, B)

This is exact (not an approximation) for a single hash function -- but a
single bit of information is too noisy.  We therefore use n INDEPENDENT hash
functions, each giving one unbiased bit.  The fraction of positions where
sig_A[i] == sig_B[i] is then an unbiased estimator of Jaccard(A, B).

Standard error: sqrt( J(1-J) / n ).  For n=100, J=0.5: stddev ~= 0.05.

IMPLEMENTATION CHOICE -- Universal Hashing:
  True independence via n separate hash functions is expensive.  We instead
  use the classic universal-hash-function family:
    h_i(x) = (a_i * x + b_i) mod p
  where p is a large prime, and a_i, b_i are drawn uniformly at random from
  [1, p-1] and [0, p-1] respectively.  We hash each shingle string to an
  integer first using Python's built-in hash (seeded for reproducibility),
  then apply the linear congruential transform.  This gives pairwise
  independence, which is sufficient for an unbiased Jaccard estimator.
"""

import hashlib
import numpy as np
from typing import Iterable


# A Mersenne prime larger than 2^32.  Using a prime as modulus ensures the
# hash function family is pairwise independent when a, b are chosen uniformly.
_LARGE_PRIME: int = (1 << 61) - 1  # 2^61 - 1, a well-known Mersenne prime


def _str_to_int(s: str) -> int:
    """Map a shingle string to a stable non-negative integer.

    We use SHA-1 (truncated to 8 bytes) instead of Python's built-in hash()
    because hash() is randomized per process by PYTHONHASHSEED.  SHA-1 is
    deterministic and reproducible across runs, which is important for the
    rebuild-index flow (we must get the same signature for the same document).

    Taking the first 8 bytes gives a 64-bit integer -- large enough that
    collisions in the shingle universe are negligible.
    """
    digest = hashlib.sha1(s.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


class MinHash:
    """MinHash signature generator.

    Holds n universal hash functions parameterized by random (a_i, b_i) pairs.
    All n functions share the same large prime modulus p = 2^61 - 1.

    Args:
        n:    Number of hash functions (= signature length).  Default 100.
        seed: RNG seed for reproducibility.  Fix this per deployment so that
              stored signatures remain valid across restarts.
    """

    def __init__(self, n: int = 100, seed: int = 42) -> None:
        self.n = n
        self.seed = seed

        rng = np.random.RandomState(seed)

        # a_i in [1, p-1], b_i in [0, p-1]
        # We use int64 arithmetic carefully to avoid overflow before modulo.
        # Because p = 2^61 - 1 > 2^60, products (a * x) can overflow int64.
        # We store as Python ints (arbitrary precision) and convert to numpy
        # only for the final signature array -- see sign() below.
        self._a: list[int] = rng.randint(1, _LARGE_PRIME, size=n).tolist()
        self._b: list[int] = rng.randint(0, _LARGE_PRIME, size=n).tolist()

    def sign(self, shingle_set: Iterable[str]) -> np.ndarray:
        """Compute the MinHash signature for a set of shingles.

        Algorithm:
          1. Map every shingle string to a 64-bit integer via SHA-1.
          2. For each hash function i, compute h_i(x) = (a_i*x + b_i) % p
             for every shingle x.
          3. sig[i] = min over all shingles of h_i(shingle).

        Args:
            shingle_set: Iterable of shingle strings (from shingling.shingle()).

        Returns:
            np.ndarray of shape (n,) with dtype uint64.
            Each entry is the minimum hash value for that hash function.
        """
        # Convert all shingles to integers once (avoid redundant SHA-1 calls)
        int_shingles: list[int] = [_str_to_int(s) for s in shingle_set]

        if not int_shingles:
            # Empty document: return all-max sentinel so comparisons give 0
            return np.full(self.n, _LARGE_PRIME, dtype=np.uint64)

        # For each of the n hash functions, find the minimum hash value.
        # We do this in pure Python to avoid int64 overflow (a*x can be > 2^63).
        # Performance is adequate for n=100 and |shingle_set| up to ~10^5.
        sig = np.empty(self.n, dtype=np.uint64)
        p = _LARGE_PRIME
        for i in range(self.n):
            a, b = self._a[i], self._b[i]
            min_val = p  # sentinel: larger than any valid hash value
            for x in int_shingles:
                h = (a * x + b) % p
                if h < min_val:
                    min_val = h
            sig[i] = min_val

        return sig


def estimated_jaccard(sig_a: np.ndarray, sig_b: np.ndarray) -> float:
    """Estimate Jaccard similarity from two MinHash signatures.

    By the probabilistic argument in the module docstring:
        E[ fraction of positions where sig_a[i] == sig_b[i] ] = Jaccard(A, B)

    This is the fast O(n) estimate we use to rank candidate pairs before
    computing the exact (and slower) Jaccard over the full shingle sets.

    Args:
        sig_a: MinHash signature of document A (np.ndarray, shape (n,)).
        sig_b: MinHash signature of document B (np.ndarray, shape (n,)).

    Returns:
        Float in [0, 1].
    """
    if len(sig_a) != len(sig_b):
        raise ValueError("Signatures must have equal length")
    return float(np.mean(sig_a == sig_b))
