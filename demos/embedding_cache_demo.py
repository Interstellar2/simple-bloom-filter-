"""
Embedding cache demo: Bloom Filter + Redis.

Scenario:
Given an input text, return its embedding vector.
Use a Bloom filter as a fast front-end to decide whether the text might be
cached in Redis:
  - Bloom filter says "definitely not cached" -> compute embedding directly.
  - Bloom filter says "might be cached"      -> check Redis.
      - Redis hit   -> return cached embedding.
      - Redis miss  -> compute embedding and write to Redis.

This demo starts Redis via Docker and uses a mock embedding model.
"""

import hashlib
import json
import subprocess
import time
from typing import List, Optional

import numpy as np
import redis

from bloom_filter import BloomFilter


class MockEmbeddingModel:
    """Mock embedding model: turns text into a deterministic fixed-dim vector."""

    def __init__(self, dim: int = 128):
        self.dim = dim

    def encode(self, text: str) -> List[float]:
        print(f"  [model compute] embedding: \"{text[:50]}...\"")
        time.sleep(0.5)  # simulate model latency

        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % (2**32)
        rng = np.random.default_rng(seed)
        vec = rng.normal(loc=0.0, scale=1.0, size=self.dim)
        vec = vec / np.linalg.norm(vec)
        return vec.tolist()


class EmbeddingCache:
    """Embedding cache layer: Bloom filter + Redis."""

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        expected_items: int = 10_000,
        false_positive_rate: float = 0.01,
        embedding_dim: int = 128,
    ):
        self.bloom = BloomFilter(expected_items, false_positive_rate)
        self.model = MockEmbeddingModel(dim=embedding_dim)
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=True,
        )
        self.embedding_dim = embedding_dim

        self.stats = {
            "bloom_filter_negative": 0,
            "bloom_filter_positive": 0,
            "redis_hit": 0,
            "redis_miss": 0,
            "model_compute": 0,
        }

    def _redis_key(self, text: str) -> str:
        return f"emb:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"

    def get_embedding(self, text: str) -> List[float]:
        print(f"\n[query] \"{text[:60]}\"")

        if text not in self.bloom:
            print("  -> Bloom filter: definitely not cached")
            self.stats["bloom_filter_negative"] += 1
            embedding = self.model.encode(text)
            self._write_to_cache(text, embedding)
            return embedding

        print("  -> Bloom filter: might be cached, checking Redis")
        self.stats["bloom_filter_positive"] += 1

        cached = self._read_from_cache(text)
        if cached is not None:
            print("  -> Redis hit \u2705")
            self.stats["redis_hit"] += 1
            return cached

        print("  -> Redis miss \u274c (Bloom filter false positive)")
        self.stats["redis_miss"] += 1
        embedding = self.model.encode(text)
        self._write_to_cache(text, embedding)
        return embedding

    def _read_from_cache(self, text: str) -> Optional[List[float]]:
        key = self._redis_key(text)
        raw = self.redis_client.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    def _write_to_cache(self, text: str, embedding: List[float]):
        key = self._redis_key(text)
        self.redis_client.set(key, json.dumps(embedding))
        self.bloom.add(text)
        self.stats["model_compute"] += 1
        print("  -> written to Redis cache")

    def print_stats(self):
        print("\n========== Statistics ==========")
        print(f"Bloom filter negative (compute directly): {self.stats['bloom_filter_negative']}")
        print(f"Bloom filter positive (check Redis):      {self.stats['bloom_filter_positive']}")
        print(f"  -> Redis hit:   {self.stats['redis_hit']}")
        print(f"  -> Redis miss (false positive): {self.stats['redis_miss']}")
        print(f"Model compute calls: {self.stats['model_compute']}")
        print("================================\n")


def start_redis():
    """Start Redis via Docker."""
    container_name = "bloom-filter-redis-demo"

    result = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name={container_name}"],
        capture_output=True,
        text=True,
    )

    if result.stdout.strip():
        print(f"Redis container '{container_name}' is already running")
        return

    print(f"Starting Redis container '{container_name}' via Docker...")
    subprocess.run(
        [
            "docker", "run", "-d",
            "--name", container_name,
            "-p", "6379:6379",
            "redis:7-alpine",
        ],
        check=True,
    )
    print("Redis container started, waiting for service...")
    time.sleep(2)


def stop_redis():
    """Stop and remove Redis container."""
    container_name = "bloom-filter-redis-demo"
    print(f"\nStopping and removing Redis container '{container_name}'...")
    subprocess.run(["docker", "stop", container_name], capture_output=True)
    subprocess.run(["docker", "rm", container_name], capture_output=True)
    print("Redis container cleaned up")


def demo():
    start_redis()

    cache = EmbeddingCache(
        redis_host="localhost",
        redis_port=6379,
        expected_items=1000,
        false_positive_rate=0.05,
        embedding_dim=128,
    )

    texts = [
        "\u4eca\u5929\u7684\u5929\u6c14\u771f\u597d",
        "\u673a\u5668\u5b66\u4e60\u662f\u4e00\u95e8\u5f88\u6709\u610f\u601d\u7684\u5b66\u79d1",
        "\u5e03\u9686\u8fc7\u6ee4\u5668\u53ef\u4ee5\u8282\u7701\u5f88\u591a\u5185\u5b58",
        "Redis is a very fast key-value database",
        "\u4eca\u5929\u7684\u5929\u6c14\u771f\u597d",  # duplicate, should hit cache
        "Python is an elegant programming language",
        "Deep learning is transforming many industries",
        "Caching can significantly improve system performance",
        "\u4eca\u5929\u7684\u5929\u6c14\u771f\u597d",  # duplicate again
    ]

    print("\n=== Start embedding queries ===")
    for text in texts:
        emb = cache.get_embedding(text)
        print(f"  first 5 dims: {[round(x, 4) for x in emb[:5]]}")

    cache.print_stats()

    # Optional cleanup: comment out to keep Redis data
    stop_redis()


if __name__ == "__main__":
    demo()
