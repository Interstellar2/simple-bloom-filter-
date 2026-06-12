"""
Benchmark: BloomFilter vs Python set.

Measures insertion and lookup throughput as well as approximate memory usage
for several dataset sizes.
"""

import random
import string
import sys
import time
from typing import Callable, List

from bloom_filter import BloomFilter


def random_string(length: int = 32, rng: random.Random = None) -> str:
    """Generate a random ASCII string."""
    if rng is None:
        rng = random
    return "".join(rng.choices(string.ascii_letters + string.digits, k=length))


def measure_time(func: Callable, *args, **kwargs) -> tuple:
    """Run func and return (result, elapsed_seconds)."""
    start = time.perf_counter()
    result = func(*args, **kwargs)
    elapsed = time.perf_counter() - start
    return result, elapsed


def benchmark_size(n: int, false_positive_rate: float = 0.01) -> dict:
    """Run a benchmark for a given number of items."""
    rng = random.Random(42)
    items = [random_string(32, rng) for _ in range(n)]
    query_items = [random_string(32, rng) for _ in range(n)]

    # Python set
    py_set, set_add_time = measure_time(set, items)
    _, set_lookup_time = measure_time(
        lambda: [item in py_set for item in query_items]
    )
    set_mem = sys.getsizeof(py_set)
    # getsizeof does not include object contents for strings; add a rough estimate.
    set_mem += sum(sys.getsizeof(s) for s in items)

    # Bloom filter
    bf = BloomFilter(expected_items=n, false_positive_rate=false_positive_rate)
    _, bf_add_time = measure_time(bf.add_many, items)
    _, bf_lookup_time = measure_time(
        lambda: [item in bf for item in query_items]
    )
    bf_mem = sys.getsizeof(bf) + bf.memory_usage_bytes()

    false_positives = sum(1 for item in query_items if item in bf)
    actual_fpp = false_positives / n

    return {
        "n": n,
        "target_fpp": false_positive_rate,
        "set_add_time": set_add_time,
        "set_lookup_time": set_lookup_time,
        "set_mem_bytes": set_mem,
        "bf_add_time": bf_add_time,
        "bf_lookup_time": bf_lookup_time,
        "bf_mem_bytes": bf_mem,
        "bf_actual_fpp": actual_fpp,
        "bf_bit_count": bf.bit_count(),
        "bf_size_bits": bf.size,
    }


def format_bytes(num_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if num_bytes < 1024.0:
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.2f} TB"


def print_results(results: List[dict]) -> None:
    print("\n" + "=" * 100)
    print(
        f"{'n':>10}  "
        f"{'Set add (ms)':>14}  "
        f"{'BF add (ms)':>14}  "
        f"{'Set lookup (ms)':>17}  "
        f"{'BF lookup (ms)':>17}  "
        f"{'Set mem':>12}  "
        f"{'BF mem':>12}  "
        f"{'Actual FPP':>12}"
    )
    print("-" * 100)
    for r in results:
        print(
            f"{r['n']:>10}  "
            f"{r['set_add_time'] * 1000:>14.2f}  "
            f"{r['bf_add_time'] * 1000:>14.2f}  "
            f"{r['set_lookup_time'] * 1000:>17.2f}  "
            f"{r['bf_lookup_time'] * 1000:>17.2f}  "
            f"{format_bytes(r['set_mem_bytes']):>12}  "
            f"{format_bytes(r['bf_mem_bytes']):>12}  "
            f"{r['bf_actual_fpp']:>12.4f}"
        )
    print("=" * 100)


def main():
    sizes = [1_000, 10_000, 100_000]
    target_fpp = 0.01

    print("Benchmarking BloomFilter vs Python set")
    print(f"Target false-positive rate: {target_fpp}")

    results = []
    for n in sizes:
        print(f"\nRunning benchmark for n={n}...")
        results.append(benchmark_size(n, target_fpp))

    print_results(results)

    print("\nNotes:")
    print("- 'Actual FPP' is measured against random query items never inserted.")
    print("- Set memory is approximate (object overhead + string contents).")
    print("- Bloom filter memory is the bit array size plus minimal object overhead.")


if __name__ == "__main__":
    main()
