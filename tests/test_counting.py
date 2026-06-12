"""Tests for the CountingBloomFilter."""

import pytest

from bloom_filter import CountingBloomFilter


class TestCountingBloomFilterInitialization:
    def test_basic_initialization(self):
        cbf = CountingBloomFilter(expected_items=1000, false_positive_rate=0.01)
        assert cbf.expected_items == 1000
        assert cbf.size > 0
        assert cbf.hash_count > 0
        assert len(cbf.counters) == cbf.size
        assert all(c == 0 for c in cbf.counters)

    def test_invalid_parameters(self):
        with pytest.raises(ValueError):
            CountingBloomFilter(expected_items=0, false_positive_rate=0.01)
        with pytest.raises(ValueError):
            CountingBloomFilter(expected_items=100, false_positive_rate=0.0)


class TestCountingBloomFilterOperations:
    def test_add_and_contains(self):
        cbf = CountingBloomFilter(expected_items=100, false_positive_rate=0.01)
        cbf.add("hello")
        assert "hello" in cbf
        assert "world" not in cbf

    def test_add_many(self):
        cbf = CountingBloomFilter(expected_items=100, false_positive_rate=0.01)
        cbf.add_many(["a", "b", "c"])
        assert all(item in cbf for item in ["a", "b", "c"])

    def test_remove(self):
        cbf = CountingBloomFilter(expected_items=100, false_positive_rate=0.01)
        cbf.add("hello")
        assert "hello" in cbf
        cbf.remove("hello")
        assert "hello" not in cbf

    def test_remove_does_not_go_negative(self):
        cbf = CountingBloomFilter(expected_items=100, false_positive_rate=0.01)
        cbf.remove("never-added")
        assert all(c == 0 for c in cbf.counters)

    def test_remove_one_of_many(self):
        cbf = CountingBloomFilter(expected_items=1000, false_positive_rate=0.01)
        cbf.add_many(["a", "b", "c"])
        cbf.remove("a")
        assert "a" not in cbf
        assert "b" in cbf
        assert "c" in cbf

    def test_false_negatives_after_removal(self):
        # Removing an item that shares counters can cause false negatives.
        cbf = CountingBloomFilter(expected_items=100, false_positive_rate=0.5)
        cbf.add("a")
        cbf.remove("a")
        assert "a" not in cbf

    def test_non_string_items(self):
        cbf = CountingBloomFilter(expected_items=100, false_positive_rate=0.01)
        cbf.add(123)
        cbf.add((4, 5, 6))
        assert 123 in cbf
        assert (4, 5, 6) in cbf
        assert 124 not in cbf


class TestCountingBloomFilterEstimates:
    def test_estimate_count(self):
        cbf = CountingBloomFilter(expected_items=1000, false_positive_rate=0.01)
        assert len(cbf) == 0
        cbf.add_many(str(i) for i in range(500))
        assert 400 < len(cbf) < 600

    def test_current_fpp_empty(self):
        cbf = CountingBloomFilter(expected_items=100, false_positive_rate=0.01)
        assert cbf.current_fpp() == 0.0


class TestCountingBloomFilterSerialization:
    def test_to_dict_from_dict(self):
        cbf = CountingBloomFilter(expected_items=500, false_positive_rate=0.05)
        cbf.add_many(["x", "y", "z"])
        data = cbf.to_dict()
        cbf2 = CountingBloomFilter.from_dict(data)
        assert cbf2.counters == cbf.counters
        assert "x" in cbf2
        assert "missing" not in cbf2

    def test_to_json_from_json(self):
        cbf = CountingBloomFilter(expected_items=500, false_positive_rate=0.05)
        cbf.add_many(["x", "y"])
        json_str = cbf.to_json()
        cbf2 = CountingBloomFilter.from_json(json_str)
        assert cbf2.counters == cbf.counters
        assert "x" in cbf2

    def test_from_dict_missing_key(self):
        with pytest.raises(ValueError, match="Missing keys"):
            CountingBloomFilter.from_dict({"expected_items": 100})
