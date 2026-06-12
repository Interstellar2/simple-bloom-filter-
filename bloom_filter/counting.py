"""
Counting Bloom Filter implementation.

A Counting Bloom Filter extends the standard Bloom Filter by replacing the
single-bit array with a counter array. This allows elements to be removed,
at the cost of increased memory usage.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Callable, Iterable, Iterator


class CountingBloomFilter:
    """A Bloom filter that supports deletion via per-bit counters.

    Each bit position is replaced by a small counter. ``add`` increments the
counters; ``remove`` decrements them. Membership is true when all relevant
counters are greater than zero.

    .. warning::
        ``remove`` on an item that was never added will decrement counters that
        may belong to other items, causing false negatives. Only remove items
        you are sure were previously added.

    Parameters
    ----------
    expected_items:
        The maximum number of items expected to be inserted.
    false_positive_rate:
        The desired false-positive probability (between 0 and 1, exclusive).
    key:
        A function that converts an arbitrary item into a ``str`` for hashing.
        Defaults to ``str``.
    """

    def __init__(
        self,
        expected_items: int,
        false_positive_rate: float,
        key: Callable[[Any], str] = str,
    ):
        if not isinstance(expected_items, int) or expected_items <= 0:
            raise ValueError("expected_items must be a positive integer")
        if not (0.0 < false_positive_rate < 1.0):
            raise ValueError("false_positive_rate must be in (0, 1)")

        self.expected_items = expected_items
        self.false_positive_rate = false_positive_rate
        self.key = key

        self.size = math.ceil(
            -(expected_items * math.log(false_positive_rate)) / (math.log(2) ** 2)
        )
        self.hash_count = max(1, math.ceil((self.size / expected_items) * math.log(2)))

        # Counter array: each slot is a non-negative integer.
        self.counters = [0] * self.size

    def _hashes(self, item: Any) -> Iterator[int]:
        """Generate ``k`` hash positions for *item* using double hashing."""
        item_bytes = self.key(item).encode("utf-8")
        # Use binary digests directly instead of hex strings for speed.
        h1 = int.from_bytes(hashlib.md5(item_bytes).digest(), "big")
        h2 = int.from_bytes(hashlib.sha1(item_bytes).digest(), "big")

        for i in range(self.hash_count):
            yield (h1 + i * h2) % self.size

    def add(self, item: Any) -> CountingBloomFilter:
        """Add a single item to the filter."""
        for pos in self._hashes(item):
            self.counters[pos] += 1
        return self

    def add_many(self, items: Iterable[Any]) -> CountingBloomFilter:
        """Add multiple items to the filter."""
        for item in items:
            self.add(item)
        return self

    def remove(self, item: Any) -> CountingBloomFilter:
        """Remove an item from the filter (decrement counters).

        This is safe only if the item was previously added.
        """
        for pos in self._hashes(item):
            if self.counters[pos] > 0:
                self.counters[pos] -= 1
        return self

    def discard(self, item: Any) -> CountingBloomFilter:
        """Alias for :meth:`remove`."""
        return self.remove(item)

    def __contains__(self, item: Any) -> bool:
        """Return ``True`` if *item* might be in the set, ``False`` if it is not."""
        return all(self.counters[pos] > 0 for pos in self._hashes(item))

    def __len__(self) -> int:
        """Estimate the number of items inserted."""
        zero_counters = self.counters.count(0)
        if zero_counters == 0:
            return self.size
        return int(-(self.size / self.hash_count) * math.log(zero_counters / self.size))

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"{self.__class__.__name__}("
            f"expected_items={self.expected_items}, "
            f"false_positive_rate={self.false_positive_rate})"
        )

    def current_fpp(self) -> float:
        """Estimate the current false-positive probability."""
        n = len(self)
        if n == 0:
            return 0.0
        return (1.0 - math.exp(-self.hash_count * n / self.size)) ** self.hash_count

    def memory_usage_bytes(self) -> int:
        """Return approximate memory footprint of the counters in bytes.

        This is a lower bound; Python lists have additional overhead.
        """
        # Each counter is a Python int; this is a rough estimate.
        return len(self.counters) * 28  # CPython small int overhead approximation

    def to_dict(self) -> dict:
        """Serialize the filter to a JSON-friendly dictionary."""
        return {
            "expected_items": self.expected_items,
            "false_positive_rate": self.false_positive_rate,
            "size": self.size,
            "hash_count": self.hash_count,
            "counters": self.counters,
        }

    @classmethod
    def from_dict(cls, data: dict, key: Callable[[Any], str] = str) -> CountingBloomFilter:
        """Deserialize a filter previously serialized with :meth:`to_dict`."""
        required = {"expected_items", "false_positive_rate", "size", "hash_count", "counters"}
        missing = required - set(data.keys())
        if missing:
            raise ValueError(f"Missing keys in serialized data: {missing}")

        instance = cls.__new__(cls)
        instance.expected_items = data["expected_items"]
        instance.false_positive_rate = data["false_positive_rate"]
        instance.size = data["size"]
        instance.hash_count = data["hash_count"]
        instance.key = key
        instance.counters = list(data["counters"])
        if len(instance.counters) != instance.size:
            raise ValueError("Counter array length does not match declared size")
        return instance

    def to_json(self, **kwargs: Any) -> str:
        """Serialize the filter to a JSON string."""
        return json.dumps(self.to_dict(), **kwargs)

    @classmethod
    def from_json(cls, data: str, key: Callable[[Any], str] = str) -> CountingBloomFilter:
        """Deserialize a filter from a JSON string."""
        return cls.from_dict(json.loads(data), key=key)
