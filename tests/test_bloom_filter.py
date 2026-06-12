"""Tests for the standard BloomFilter."""

import random

import pytest

from bloom_filter import BloomFilter


class TestBloomFilterInitialization:
    def test_basic_initialization(self):
        bf = BloomFilter(expected_items=1000, false_positive_rate=0.01)
        assert bf.expected_items == 1000
        assert bf.false_positive_rate == 0.01
        assert bf.size > 0
        assert bf.hash_count > 0
        assert len(bf.bit_array) == bf.size

    def test_invalid_expected_items(self):
        with pytest.raises(ValueError, match="expected_items must be a positive integer"):
            BloomFilter(expected_items=0, false_positive_rate=0.01)
        with pytest.raises(ValueError, match="expected_items must be a positive integer"):
            BloomFilter(expected_items=-1, false_positive_rate=0.01)

    def test_invalid_false_positive_rate(self):
        with pytest.raises(ValueError, match="false_positive_rate must be in \\(0, 1\\)"):
            BloomFilter(expected_items=1000, false_positive_rate=0.0)
        with pytest.raises(ValueError, match="false_positive_rate must be in \\(0, 1\\)"):
            BloomFilter(expected_items=1000, false_positive_rate=1.0)
        with pytest.raises(ValueError, match="false_positive_rate must be in \\(0, 1\\)"):
            BloomFilter(expected_items=1000, false_positive_rate=-0.1)


class TestBloomFilterMembership:
    def test_no_false_negatives(self):
        bf = BloomFilter(expected_items=1000, false_positive_rate=0.01)
        items = [f"item-{i}" for i in range(1000)]
        bf.add_many(items)
        for item in items:
            assert item in bf

    def test_add_single_and_contains(self):
        bf = BloomFilter(expected_items=100, false_positive_rate=0.01)
        bf.add("hello")
        assert "hello" in bf
        assert "world" not in bf

    def test_add_many(self):
        bf = BloomFilter(expected_items=100, false_positive_rate=0.01)
        bf.add_many(["a", "b", "c"])
        assert "a" in bf
        assert "b" in bf
        assert "c" in bf
        assert "d" not in bf

    def test_non_string_items(self):
        bf = BloomFilter(expected_items=100, false_positive_rate=0.01)
        bf.add(42)
        bf.add((1, 2, 3))
        assert 42 in bf
        assert (1, 2, 3) in bf
        assert 43 not in bf

    def test_chaining(self):
        bf = BloomFilter(expected_items=100, false_positive_rate=0.01)
        result = bf.add("x").add_many(["y", "z"])
        assert result is bf
        assert "x" in bf
        assert "z" in bf


class TestBloomFilterEstimates:
    def test_estimate_count(self):
        bf = BloomFilter(expected_items=1000, false_positive_rate=0.01)
        assert len(bf) == 0
        bf.add_many(str(i) for i in range(500))
        # Estimate should be reasonably close to 500.
        assert 450 < len(bf) < 550

    def test_current_fpp_empty(self):
        bf = BloomFilter(expected_items=1000, false_positive_rate=0.01)
        assert bf.current_fpp() == 0.0

    def test_current_fpp_after_insertions(self):
        bf = BloomFilter(expected_items=1000, false_positive_rate=0.01)
        bf.add_many(str(i) for i in range(1000))
        assert bf.current_fpp() > 0
        assert bf.current_fpp() < 0.05


class TestBloomFilterSerialization:
    def test_to_bytes_from_bytes(self):
        bf = BloomFilter(expected_items=1000, false_positive_rate=0.01)
        bf.add_many(["a", "b", "c"])
        data = bf.to_bytes()
        bf2 = BloomFilter.from_bytes(data)
        assert bf2.size == bf.size
        assert bf2.hash_count == bf.hash_count
        assert bf2.bit_array == bf.bit_array
        assert "a" in bf2
        assert "d" not in bf2

    def test_to_dict_from_dict(self):
        bf = BloomFilter(expected_items=500, false_positive_rate=0.05)
        bf.add_many(["x", "y"])
        data = bf.to_dict()
        bf2 = BloomFilter.from_dict(data)
        assert bf2.size == bf.size
        assert bf2.bit_array == bf.bit_array
        assert "x" in bf2
        assert "z" not in bf2

    def test_from_bytes_invalid_magic(self):
        # Header is 28 bytes; provide enough data but wrong magic bytes.
        with pytest.raises(ValueError, match="Invalid BloomFilter serialization magic bytes"):
            BloomFilter.from_bytes(b"BAD!" + b"\x00" * 24)

    def test_from_bytes_too_short(self):
        with pytest.raises(ValueError, match="Data too short"):
            BloomFilter.from_bytes(b"\x00\x00")


class TestBloomFilterSetOperations:
    def test_union(self):
        bf1 = BloomFilter(expected_items=1000, false_positive_rate=0.01)
        bf2 = BloomFilter(expected_items=1000, false_positive_rate=0.01)
        bf1.add("a")
        bf2.add("b")
        bf3 = bf1.union(bf2)
        assert "a" in bf3
        assert "b" in bf3

    def test_union_incompatible_config(self):
        bf1 = BloomFilter(expected_items=1000, false_positive_rate=0.01)
        bf2 = BloomFilter(expected_items=2000, false_positive_rate=0.01)
        with pytest.raises(ValueError, match="same size and hash count"):
            bf1.union(bf2)

    def test_intersection(self):
        bf1 = BloomFilter(expected_items=1000, false_positive_rate=0.01)
        bf2 = BloomFilter(expected_items=1000, false_positive_rate=0.01)
        bf1.add_many(["a", "b"])
        bf2.add_many(["b", "c"])
        bf3 = bf1.intersection(bf2)
        assert "b" in bf3


class TestBloomFilterFalsePositiveRate:
    def test_false_positive_rate_within_target(self):
        expected_items = 5000
        target_fpp = 0.01
        bf = BloomFilter(expected_items=expected_items, false_positive_rate=target_fpp)
        inserted = [f"item-{i}" for i in range(expected_items)]
        bf.add_many(inserted)

        random.seed(42)
        false_positives = 0
        trials = 10_000
        for _ in range(trials):
            candidate = f"not-inserted-{random.randint(10**6, 10**9)}"
            if candidate in bf:
                false_positives += 1

        actual_fpp = false_positives / trials
        # Allow a generous margin because this is a randomized test.
        assert actual_fpp < target_fpp * 2.5
