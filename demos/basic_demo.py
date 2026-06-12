"""
Basic Bloom Filter demo: check whether a URL has been visited.
"""

import random

from bloom_filter import BloomFilter


def demo():
    # 1. Initialize the Bloom filter
    bf = BloomFilter(expected_items=10_000, false_positive_rate=0.01)

    print("Bloom filter initialized:")
    print(f"  expected items n={bf.expected_items}, target fpp p={bf.false_positive_rate}")
    print(f"  bit array size m={bf.size} bits ({bf.memory_usage_bytes() / 1024:.2f} KB)")
    print(f"  hash function count k={bf.hash_count}\n")

    # 2. Simulate visited URLs
    visited_urls = [
        "https://www.google.com",
        "https://www.github.com",
        "https://www.example.com/page1",
        "https://www.example.com/page2",
        "https://news.ycombinator.com",
        "https://www.python.org",
        "https://stackoverflow.com/questions/1",
        "https://stackoverflow.com/questions/2",
        "https://www.wikipedia.org",
        "https://www.reddit.com",
    ]

    print("Adding visited URLs to the Bloom filter...")
    bf.add_many(visited_urls)
    for url in visited_urls:
        print(f"  + {url}")

    # 3. Query visited URLs
    print("\n=== Query visited URLs ===")
    for url in visited_urls:
        result = url in bf
        print(f"{url}: {'might exist ✅' if result else 'definitely not ❌'}")

    # 4. Query unvisited URLs
    not_visited_urls = [
        "https://www.this-does-not-exist-12345.com",
        "https://www.another-fake-site-67890.com",
        "https://www.never-visited.com/page",
    ]

    print("\n=== Query unvisited URLs ===")
    for url in not_visited_urls:
        result = url in bf
        print(f"{url}: {'might exist ⚠️ (possible false positive)' if result else 'definitely not ✅'}")

    # 5. False positive rate test with random URLs
    print("\n=== False positive rate test ===")
    test_count = 10_000
    random.seed(42)
    false_positives = 0

    for _ in range(test_count):
        fake_url = f"https://www.fake-site-{random.randint(10**6, 10**9)}.com"
        if fake_url in bf:
            false_positives += 1

    actual_rate = false_positives / test_count
    print(f"Random URL test count: {test_count}")
    print(f"False positives: {false_positives}")
    print(f"Actual false positive rate: {actual_rate:.4f} ({actual_rate * 100:.2f}%)")
    print(f"Target false positive rate: {bf.false_positive_rate:.4f} ({bf.false_positive_rate * 100:.2f}%)")
    print(f"Estimated inserted items: {len(bf)}")
    print(f"Current estimated fpp: {bf.current_fpp():.4f}")

    # 6. Serialization demo
    print("\n=== Serialization demo ===")
    serialized = bf.to_bytes()
    bf2 = BloomFilter.from_bytes(serialized)
    print(f"Serialized size: {len(serialized)} bytes")
    print(f"Deserialized filter matches original: {bf2.bit_array == bf.bit_array}")
    print(f"'https://www.google.com' in deserialized: {'https://www.google.com' in bf2}")


if __name__ == "__main__":
    demo()
