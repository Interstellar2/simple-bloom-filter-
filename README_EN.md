# simple-bloom-filter

[![Python Versions](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A simple, dependency-light Bloom Filter implementation in Python.

- [中文 README](./README.md)

---

## What is a Bloom Filter?

A Bloom filter is a space-efficient probabilistic data structure used to test
whether an element is a member of a set. It may return **false positives**, but
it never returns **false negatives**.

In other words:

- If the filter says "definitely not in the set", you can trust it.
- If the filter says "might be in the set", you should double-check with a
  definitive source (e.g., a database, Redis, etc.).

This makes Bloom filters ideal as a fast pre-filter in front of slower storage
layers.

---

## Installation

### From source (recommended during development)

```bash
git clone https://github.com/yourname/simple-bloom-filter.git
cd simple-bloom-filter
pip install -e .
```

### Optional dependencies

The core library has **no external dependencies**. Optional extras are available for demos:

- `redis` for the Redis-backed embedding cache demo.
- `multimodal` for the image fingerprint deduplication demo (Pillow only).

```bash
pip install -e ".[redis]"
# or
pip install -e ".[multimodal]"
```

### Development dependencies

```bash
pip install -e ".[dev]"
```

---

## Quick Start

```python
from bloom_filter import BloomFilter

bf = BloomFilter(expected_items=10_000, false_positive_rate=0.01)

bf.add("https://www.google.com")
bf.add_many([
    "https://www.github.com",
    "https://www.python.org",
])

print("https://www.google.com" in bf)   # True  (might be present)
print("https://www.example.com" in bf)  # False (definitely not present)
```

### Serialization

```python
# Serialize to bytes
data = bf.to_bytes()
bf2 = BloomFilter.from_bytes(data)

# Or use JSON-friendly dict format
state = bf.to_dict()
bf3 = BloomFilter.from_dict(state)
```

### Counting Bloom Filter (supports deletion)

```python
from bloom_filter import CountingBloomFilter

cbf = CountingBloomFilter(expected_items=1000, false_positive_rate=0.01)
cbf.add("hello")
print("hello" in cbf)  # True

cbf.remove("hello")
print("hello" in cbf)  # False
```

> **Warning:** Only remove items you are sure were previously added. Removing an
> item that was never inserted can decrement counters shared by other items and
> cause false negatives.

---

## API Reference

### `BloomFilter`

```python
BloomFilter(
    expected_items: int,
    false_positive_rate: float,
    key: Callable[[Any], str] = str,
)
```

| Parameter | Description |
|-----------|-------------|
| `expected_items` | Maximum number of items you expect to insert. |
| `false_positive_rate` | Desired false-positive probability, e.g., `0.01` for 1%. |
| `key` | Function converting an arbitrary item to a `str` for hashing. |

#### Methods

| Method | Description |
|--------|-------------|
| `add(item)` | Insert a single item. Returns the filter for chaining. |
| `add_many(items)` | Insert multiple items. |
| `__contains__(item)` | Check membership (`item in bf`). |
| `__len__()` | Estimate the number of inserted items. |
| `current_fpp()` | Estimate the current false-positive probability. |
| `bit_count()` | Number of bits currently set to 1. |
| `memory_usage_bytes()` | Memory footprint of the bit array. |
| `to_bytes()` | Serialize to bytes. |
| `from_bytes(data)` | Deserialize from bytes. |
| `to_dict()` | Serialize to a JSON-friendly dict. |
| `from_dict(data)` | Deserialize from a dict. |
| `union(other)` | Return the union of two filters with identical config. |
| `intersection(other)` | Return the intersection of two filters. |

### `CountingBloomFilter`

Same constructor as `BloomFilter`, with additional methods:

| Method | Description |
|--------|-------------|
| `remove(item)` | Decrement counters for an item (deletion). |
| `discard(item)` | Alias for `remove`. |
| `to_json()` | Serialize to a JSON string. |
| `from_json(data)` | Deserialize from a JSON string. |

---

## Example: Bloom Filter + Redis Embedding Cache

A common production pattern is using a Bloom filter as a lightweight guard in
front of a Redis cache.

See [demos/embedding_cache_demo.py](./demos/embedding_cache_demo.py) for a
complete runnable example that starts Redis via Docker, mocks an embedding
model, and shows how many Redis lookups the Bloom filter avoids.

Run it with:

```bash
pip install -e ".[redis]"
python demos/embedding_cache_demo.py
```

---

## Example: Image Fingerprint Deduplication

Bloom filters can also act as a fast pre-filter for multimodal content. This
example shows **image fingerprint presence filtering** using only Pillow.

### Scenario: rejecting duplicate image uploads

When a user uploads an image, the platform wants to reject it quickly if the
same (or near-identical) image has been seen before. Instead of storing full
images or large feature vectors, we compute a compact **perceptual hash**
(a.k.a. fingerprint) and store it in a Bloom filter:

```text
uploaded image
      ↓
compute perceptual hash fingerprint
      ↓
Bloom filter
      ↓ definitely new
accept upload
      ↓ might be a duplicate
compare fingerprint against exact store
      ↓ exact match exists
reject upload (duplicate)
      ↓ Bloom filter false positive
accept upload and record fingerprint
```

### Important caveats

- This is **fingerprint presence filtering**, not reverse-image search or
  semantic similarity retrieval.
- Perceptual hashes are robust to resizing, re-encoding, and minor brightness
  changes, but hash collisions and Bloom filter false positives can still occur.
- Any "might be a duplicate" result from the Bloom filter must be confirmed by
  an exact store before rejecting the upload.

### Run it

```bash
pip install -e ".[multimodal]"
python demos/multimodal_image_dedup_demo.py
```

The demo generates synthetic images with Pillow, computes a 256-bit simplified
perceptual hash for each, and uses the Bloom filter as a front-end for an
in-memory exact store. It then queries:

- the original images (exact matches),
- resized + JPEG-recompressed variants (should still match),
- brand-new images (should be reported as new).

Full source: [demos/multimodal_image_dedup_demo.py](./demos/multimodal_image_dedup_demo.py)

---

## Benchmarks

A benchmark comparing `BloomFilter` with Python `set` is included in
[benchmarks/benchmark.py](./benchmarks/benchmark.py).

```bash
python benchmarks/benchmark.py
```

Typical output (target FPP = 1%):

```text
         n    Set add (ms)     BF add (ms)    Set lookup (ms)     BF lookup (ms)       Set mem        BF mem    Actual FPP
------------------------------------------------------------------------------------------------------------------------------------
      1000            0.03            1.77               0.04               1.98     103.50 KB       9.41 KB        0.0110
     10000            0.33           17.91               0.32              17.77       1.20 MB      93.65 KB        0.0100
    100000            4.62          177.77               4.05             178.69      10.96 MB     936.09 KB        0.0103
```

Notes:

- Python `set` is implemented in C and is much faster for small-to-medium
  workloads.
- `BloomFilter` uses dramatically less memory (roughly **10\~20x** in this
  benchmark) and scales independently of the item size.
- Use a Bloom filter when memory is constrained or when the items themselves
  are large (e.g., URLs, long strings, embedding cache keys).

---

## Project Structure

```text
.
├── bloom_filter/             # Core package
│   ├── __init__.py
│   ├── core.py               # Standard BloomFilter
│   └── counting.py           # CountingBloomFilter
├── demos/                    # Runnable examples
│   ├── basic_demo.py
│   ├── embedding_cache_demo.py
│   └── multimodal_image_dedup_demo.py
├── tests/                    # pytest suite
│   ├── test_bloom_filter.py
│   └── test_counting.py
├── benchmarks/               # Performance benchmarks
│   └── benchmark.py
├── README.md                 # Chinese documentation
├── README_EN.md              # English documentation
├── pyproject.toml            # Packaging and tool configuration
└── .gitignore
```

---

## Running Tests

```bash
pytest
```

With coverage:

```bash
pytest --cov=bloom_filter --cov-report=term-missing
```

---

## Linting and Type Checking

```bash
ruff check .
mypy bloom_filter
```

---

## License

This project is licensed under the [MIT License](./LICENSE).

---

## Contributing

Contributions are welcome! Please open an issue or pull request if you have
ideas for improvements, additional filter variants, or bug fixes.
