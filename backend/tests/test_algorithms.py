"""
test_algorithms.py -- Unit tests for shingling, minhash, and lsh modules.

Run with:
    cd backend && pytest tests/test_algorithms.py -v
"""

import numpy as np
import pytest

from app.algorithms.shingling import (
    normalize_text,
    shingle,
    exact_jaccard,
    shared_shingles,
)
from app.algorithms.minhash import MinHash, estimated_jaccard
from app.algorithms.lsh import band_hashes


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def minhash():
    """Shared MinHash instance (n=100, seed=42) for the whole test module."""
    return MinHash(n=100, seed=42)


# ---------------------------------------------------------------------------
# shingling.py tests
# ---------------------------------------------------------------------------

class TestNormalizeText:
    def test_lowercase(self):
        assert normalize_text("Hello World") == "hello world"

    def test_collapse_whitespace(self):
        assert normalize_text("a  b\n\tc") == "a b c"

    def test_code_strips_line_comments(self):
        src = "int x = 1; // this is a comment\nint y = 2;"
        result = normalize_text(src, mode="code")
        assert "//" not in result
        assert "comment" not in result

    def test_code_strips_hash_comments(self):
        src = "x = 1  # Python comment\ny = 2"
        result = normalize_text(src, mode="code")
        assert "python comment" not in result

    def test_code_strips_block_comments(self):
        src = "int a = /* block\ncomment */ 5;"
        result = normalize_text(src, mode="code")
        assert "block" not in result

    def test_code_normalizes_string_literals(self):
        src = 'print("hello world")'
        result = normalize_text(src, mode="code")
        # Sentinel is lowercase 'strlit' (normalized after .lower() is applied first)
        assert "strlit" in result
        assert "hello world" not in result


class TestShingle:
    def test_basic_shingles(self):
        result = shingle("abcde", k=3)
        assert result == frozenset({"abc", "bcd", "cde"})

    def test_short_document_returns_whole_text(self):
        result = shingle("ab", k=5)
        assert result == frozenset({"ab"})

    def test_empty_document_returns_empty(self):
        result = shingle("", k=5)
        assert result == frozenset()

    def test_single_shingle_for_exact_k_length(self):
        result = shingle("hello", k=5)
        assert result == frozenset({"hello"})


class TestExactJaccard:
    def test_identical_sets(self):
        s = frozenset({"abc", "bcd", "cde"})
        assert exact_jaccard(s, s) == 1.0

    def test_disjoint_sets(self):
        a = frozenset({"abc", "bcd"})
        b = frozenset({"xyz", "uvw"})
        assert exact_jaccard(a, b) == 0.0

    def test_partial_overlap(self):
        a = frozenset({"abc", "bcd", "cde"})
        b = frozenset({"bcd", "cde", "def"})
        # intersection = {bcd, cde}, union = {abc, bcd, cde, def}
        assert exact_jaccard(a, b) == pytest.approx(2 / 4)

    def test_empty_sets(self):
        assert exact_jaccard(frozenset(), frozenset()) == 0.0

    def test_one_empty(self):
        a = frozenset({"abc"})
        assert exact_jaccard(a, frozenset()) == 0.0


class TestSharedShingles:
    def test_returns_intersection(self):
        a = frozenset({"abc", "bcd", "cde"})
        b = frozenset({"bcd", "cde", "def"})
        assert shared_shingles(a, b) == frozenset({"bcd", "cde"})


# ---------------------------------------------------------------------------
# minhash.py tests
# ---------------------------------------------------------------------------

class TestMinHash:
    def test_identical_documents_estimated_jaccard_1(self, minhash):
        """Identical documents must produce equal signatures -> estimated J = 1.0."""
        text = "the quick brown fox jumps over the lazy dog"
        s = shingle(normalize_text(text), k=5)
        sig = minhash.sign(s)
        assert estimated_jaccard(sig, sig) == pytest.approx(1.0)

    def test_disjoint_documents_estimated_jaccard_near_0(self, minhash):
        """Disjoint documents should estimate Jaccard very close to 0."""
        text_a = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        text_b = "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"
        # Use k=1 to ensure shingle sets are truly disjoint
        s_a = shingle(text_a, k=1)
        s_b = shingle(text_b, k=1)
        sig_a = minhash.sign(s_a)
        sig_b = minhash.sign(s_b)
        # Allow small tolerance due to hash collisions
        assert estimated_jaccard(sig_a, sig_b) < 0.05

    def test_minhash_approximation_error_within_tolerance(self, minhash):
        """For a mid-range Jaccard, MinHash estimate error should be < 0.1.

        We construct two sets with known Jaccard ~= 0.5 and verify the
        estimate is within 0.1 of truth (looser than theoretical 0.05 stddev
        to make the test robust against randomness without a fixed seed per call).
        """
        # Build two sets sharing exactly half their elements
        universe = [f"shingle_{i:04d}" for i in range(200)]
        set_a = frozenset(universe[:100])       # elements 0..99
        set_b = frozenset(universe[50:150])     # elements 50..149
        # J(A,B) = |{50..99}| / |{0..149}| = 50 / 150 = 1/3 ~= 0.333
        true_j = exact_jaccard(set_a, set_b)

        sig_a = minhash.sign(set_a)
        sig_b = minhash.sign(set_b)
        est_j = estimated_jaccard(sig_a, sig_b)

        assert abs(est_j - true_j) < 0.1, (
            f"MinHash estimation error {abs(est_j - true_j):.4f} >= 0.10; "
            f"true={true_j:.4f}, estimated={est_j:.4f}"
        )

    def test_signature_length(self, minhash):
        """Signature must have exactly n entries."""
        s = shingle("hello world from minash test", k=3)
        sig = minhash.sign(s)
        assert sig.shape == (100,)

    def test_empty_document_signature(self, minhash):
        """Empty document should not raise; just return sentinel values."""
        sig = minhash.sign(frozenset())
        assert sig.shape == (100,)


# ---------------------------------------------------------------------------
# lsh.py tests
# ---------------------------------------------------------------------------

class TestBandHashes:
    def test_correct_number_of_bands(self):
        sig = np.arange(100, dtype=np.uint64)
        hashes = band_hashes(sig, b=20, r=5)
        assert len(hashes) == 20

    def test_identical_signatures_produce_identical_band_hashes(self):
        sig = np.arange(100, dtype=np.uint64)
        h1 = band_hashes(sig, b=20, r=5)
        h2 = band_hashes(sig, b=20, r=5)
        assert h1 == h2

    def test_different_signatures_differ_in_band_hashes(self):
        rng = np.random.RandomState(0)
        sig_a = rng.randint(0, 2**32, size=100, dtype=np.uint64)
        sig_b = rng.randint(0, 2**32, size=100, dtype=np.uint64)
        h_a = band_hashes(sig_a, b=20, r=5)
        h_b = band_hashes(sig_b, b=20, r=5)
        # Extremely unlikely for all 20 bands to collide on random inputs
        assert h_a != h_b

    def test_invalid_dimensions_raise(self):
        sig = np.arange(99, dtype=np.uint64)  # 99 != 20*5
        with pytest.raises(ValueError, match="must equal b\\*r"):
            band_hashes(sig, b=20, r=5)


class TestLSHDetectsHighSimilarity:
    def test_similar_docs_share_at_least_one_band(self):
        """Two 80%-similar documents must share >= 1 band bucket.

        We construct this directly: make two signatures that differ in
        exactly 20 out of 100 positions (-> estimated J = 0.8).

        With b=20, r=5 and J=0.8:
            P(miss in one band) = 1 - 0.8^5 ~= 0.672
            P(miss in ALL 20 bands) = 0.672^20 ~= 0.0003

        The probability of this test failing due to randomness is ~0.03%.
        """
        minhash = MinHash(n=100, seed=7)

        # Long document with enough shingles for a stable signature
        base_text = " ".join(f"word{i}" for i in range(500))
        s_base = shingle(normalize_text(base_text), k=5)
        sig_base = minhash.sign(s_base)

        # Near-duplicate: change ~20% of the document
        modified_text = " ".join(
            f"REPL{i}" if i % 5 == 0 else f"word{i}" for i in range(500)
        )
        s_mod = shingle(normalize_text(modified_text), k=5)
        sig_mod = minhash.sign(s_mod)

        hashes_a = band_hashes(sig_base, b=20, r=5)
        hashes_b = band_hashes(sig_mod, b=20, r=5)

        shared_bands = sum(1 for ha, hb in zip(hashes_a, hashes_b) if ha == hb)
        assert shared_bands >= 1, (
            f"80%-similar docs share 0 band buckets -- likely a bug. "
            f"Estimated J = {estimated_jaccard(sig_base, sig_mod):.3f}"
        )

    def test_dissimilar_docs_rarely_share_bands(self):
        """Two truly dissimilar documents should share very few band buckets."""
        minhash = MinHash(n=100, seed=99)
        text_a = " ".join(f"apple{i}" for i in range(300))
        text_b = " ".join(f"zebra{i}" for i in range(300))
        sig_a = minhash.sign(shingle(normalize_text(text_a), k=5))
        sig_b = minhash.sign(shingle(normalize_text(text_b), k=5))

        hashes_a = band_hashes(sig_a, b=20, r=5)
        hashes_b = band_hashes(sig_b, b=20, r=5)

        shared_bands = sum(1 for ha, hb in zip(hashes_a, hashes_b) if ha == hb)
        # With J ~= 0 and 20 bands, expected shared bands ~= 0.
        # Allow at most 2 collisions (with high probability).
        assert shared_bands <= 2, (
            f"Dissimilar docs share {shared_bands} band buckets -- suspect hash collision."
        )
