"""
Core Bloom Filter implementation.

A Bloom filter is a space-efficient probabilistic data structure used to test
whether an element is a member of a set. False positives are possible, but
false negatives are not.
"""

from __future__ import annotations

import hashlib
import math
import struct
from typing import Any, Callable, Iterable, Iterator

# Binary format for serialization:
#   - magic      : 4 bytes  b"PYBF"
#   - version    : 1 byte   0x01
#   - reserved   : 3 bytes  0x00
#   - n          : 4 bytes  uint32  expected_items
#   - p          : 8 bytes  float64 false_positive_rate
#   - m          : 4 bytes  uint32  bit array size
#   - k          : 4 bytes  uint32  hash count
#   - bit_array  : m bytes
_SERIAL_MAGIC = b"PYBF"
_SERIAL_VERSION = 1
_SERIAL_HEADER = struct.Struct(
    "!4s B 3s I d I I"
)  # magic, version, reserved, n, p, m, k


class BloomFilter:
    """A memory-efficient Bloom filter for membership queries.

    Parameters
    ----------
    expected_items:
        The maximum number of items expected to be inserted.
    false_positive_rate:
        The desired false-positive probability (between 0 and 1, exclusive).
    key:
        A function that converts an arbitrary item into a ``str`` for hashing.
        Defaults to ``str``.

    Examples
    --------
    >>> bf = BloomFilter(expected_items=1000, false_positive_rate=0.01)
    >>> bf.add("hello")
    >>> "hello" in bf
    True
    >>> "world" in bf
    False
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

        # Optimal bit array size m and number of hash functions k.
        # m = - (n * ln(p)) / (ln(2)^2)
        # k = (m / n) * ln(2)
        self.size = math.ceil(
            -(expected_items * math.log(false_positive_rate)) / (math.log(2) ** 2)
        )
        self.hash_count = max(1, math.ceil((self.size / expected_items) * math.log(2)))

        # Bit array stored as a bytearray for memory efficiency.
        self.bit_array = bytearray(self.size)

    def _hashes(self, item: Any) -> Iterator[int]:
        """Generate ``k`` hash positions for *item* using double hashing."""
        item_bytes = self.key(item).encode("utf-8")
        # Use binary digests directly instead of hex strings for speed.
        h1 = int.from_bytes(hashlib.md5(item_bytes).digest(), "big")
        h2 = int.from_bytes(hashlib.sha1(item_bytes).digest(), "big")

        for i in range(self.hash_count):
            yield (h1 + i * h2) % self.size

    def add(self, item: Any) -> BloomFilter:
        """Add a single item to the filter.

        Returns the filter instance to allow chaining.
        """
        for pos in self._hashes(item):
            self.bit_array[pos] = 1
        return self

    def add_many(self, items: Iterable[Any]) -> BloomFilter:
        """Add multiple items to the filter."""
        for item in items:
            self.add(item)
        return self

    def __contains__(self, item: Any) -> bool:
        """Return ``True`` if *item* might be in the set, ``False`` if it is not."""
        return all(self.bit_array[pos] == 1 for pos in self._hashes(item))

    def __len__(self) -> int:
        """Estimate the number of items inserted.

        This is an approximation based on the ratio of unset bits.
        """
        unset_bits = self.bit_array.count(0)
        if unset_bits == 0:
            return self.size
        return int(-(self.size / self.hash_count) * math.log(unset_bits / self.size))

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"{self.__class__.__name__}("
            f"expected_items={self.expected_items}, "
            f"false_positive_rate={self.false_positive_rate})"
        )

    def current_fpp(self) -> float:
        """Estimate the current false-positive probability.

        Based on the current fill ratio of the bit array and the number of
        estimated items inserted.
        """
        n = len(self)
        if n == 0:
            return 0.0
        return (1.0 - math.exp(-self.hash_count * n / self.size)) ** self.hash_count

    def bit_count(self) -> int:
        """Return the number of bits currently set to 1."""
        return sum(self.bit_array)

    def memory_usage_bytes(self) -> int:
        """Return the memory footprint of the bit array in bytes."""
        return len(self.bit_array)

    def to_bytes(self) -> bytes:
        """Serialize the filter to bytes."""
        return (
            _SERIAL_HEADER.pack(
                _SERIAL_MAGIC,
                _SERIAL_VERSION,
                b"\x00\x00\x00",
                self.expected_items,
                self.false_positive_rate,
                self.size,
                self.hash_count,
            )
            + bytes(self.bit_array)
        )

    @classmethod
    def from_bytes(cls, data: bytes, key: Callable[[Any], str] = str) -> BloomFilter:
        """Deserialize a filter previously serialized with :meth:`to_bytes`."""
        header_size = _SERIAL_HEADER.size
        if len(data) < header_size:
            raise ValueError("Data too short to contain a serialized BloomFilter")

        magic, version, _reserved, n, p, m, k = _SERIAL_HEADER.unpack(
            data[:header_size]
        )
        if magic != _SERIAL_MAGIC:
            raise ValueError("Invalid BloomFilter serialization magic bytes")
        if version != _SERIAL_VERSION:
            raise ValueError(f"Unsupported BloomFilter serialization version {version}")

        bit_array = data[header_size:]
        if len(bit_array) != m:
            raise ValueError(
                f"Bit array length mismatch: expected {m}, got {len(bit_array)}"
            )

        # Build instance directly to avoid re-computing size/k.
        instance = cls.__new__(cls)
        instance.expected_items = n
        instance.false_positive_rate = p
        instance.size = m
        instance.hash_count = k
        instance.key = key
        instance.bit_array = bytearray(bit_array)
        return instance

    def to_dict(self) -> dict:
        """Serialize the filter to a JSON-friendly dictionary."""
        return {
            "expected_items": self.expected_items,
            "false_positive_rate": self.false_positive_rate,
            "size": self.size,
            "hash_count": self.hash_count,
            "bit_array": self.bit_array.hex(),
        }

    @classmethod
    def from_dict(cls, data: dict, key: Callable[[Any], str] = str) -> BloomFilter:
        """Deserialize a filter previously serialized with :meth:`to_dict`."""
        required = {"expected_items", "false_positive_rate", "size", "hash_count", "bit_array"}
        missing = required - set(data.keys())
        if missing:
            raise ValueError(f"Missing keys in serialized data: {missing}")

        instance = cls.__new__(cls)
        instance.expected_items = data["expected_items"]
        instance.false_positive_rate = data["false_positive_rate"]
        instance.size = data["size"]
        instance.hash_count = data["hash_count"]
        instance.key = key
        instance.bit_array = bytearray.fromhex(data["bit_array"])
        if len(instance.bit_array) != instance.size:
            raise ValueError("Bit array length does not match declared size")
        return instance

    def union(self, other: BloomFilter) -> BloomFilter:
        """Return a new BloomFilter representing the union of two filters.

        Both filters must have identical configuration (size and hash_count).
        """
        if not isinstance(other, BloomFilter):
            raise TypeError("Can only union with another BloomFilter")
        if self.size != other.size or self.hash_count != other.hash_count:
            raise ValueError("BloomFilters must have the same size and hash count")

        result = self.__new__(self.__class__)
        result.expected_items = self.expected_items
        result.false_positive_rate = self.false_positive_rate
        result.size = self.size
        result.hash_count = self.hash_count
        result.key = self.key
        result.bit_array = bytearray(
            a | b for a, b in zip(self.bit_array, other.bit_array)
        )
        return result

    def intersection(self, other: BloomFilter) -> BloomFilter:
        """Return a new BloomFilter representing the intersection of two filters."""
        if not isinstance(other, BloomFilter):
            raise TypeError("Can only intersect with another BloomFilter")
        if self.size != other.size or self.hash_count != other.hash_count:
            raise ValueError("BloomFilters must have the same size and hash count")

        result = self.__new__(self.__class__)
        result.expected_items = self.expected_items
        result.false_positive_rate = self.false_positive_rate
        result.size = self.size
        result.hash_count = self.hash_count
        result.key = self.key
        result.bit_array = bytearray(
            a & b for a, b in zip(self.bit_array, other.bit_array)
        )
        return result
