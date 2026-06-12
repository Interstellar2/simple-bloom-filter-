"""
Multimodal image fingerprint presence demo.

Scenario:
    A content platform wants to reject uploads that have already been seen.
    Computing an exact perceptual hash for every image is cheap, but storing
    all hashes in a database grows without bound. A Bloom filter acts as a
    tiny, fast front-end:

      - Bloom filter says "definitely not seen" -> accept the upload.
      - Bloom filter says "might be seen"       -> compare the exact
        fingerprint against a backing store to confirm.

Important limitation:
    This is *presence* filtering on a perceptual fingerprint. It answers
    "have I seen this exact (or near-exact) fingerprint before?" It is NOT
    a semantic similarity search: a visually different image with a
    coincidentally similar fingerprint can still trigger a false positive.

This demo only requires Pillow (no numpy / imagehash).
"""

from __future__ import annotations

import io
import random
from pathlib import Path

from bloom_filter import BloomFilter

try:
    from PIL import Image, ImageDraw
except ImportError as exc:  # pragma: no cover - optional dependency
    raise ImportError(
        "This demo requires Pillow. Install it with: pip install -e '.[multimodal]'"
    ) from exc


def simple_phash(image: Image.Image, size: int = 16) -> str:
    """Compute a compact perceptual hash using only Pillow.

    Steps:
        1. Convert to grayscale.
        2. Resize to ``size x size`` with a high-quality filter.
        3. Compare each pixel to the mean brightness.
        4. Return the resulting bit string as a hex fingerprint.

    This is essentially an ``aHash`` variant. It is robust to mild
    resizing, re-encoding, and small brightness shifts, but it is still
    just a demo-quality fingerprint.
    """
    gray = image.convert("L").resize((size, size), Image.Resampling.LANCZOS)
    pixels = list(gray.getdata())
    mean = sum(pixels) / len(pixels)
    bits = "".join("1" if p >= mean else "0" for p in pixels)
    return hex(int(bits, 2))[2:].upper().zfill(size * size // 4)


class ImageFingerprintDedup:
    """Fast image deduplication front-end: Bloom filter + exact store."""

    def __init__(
        self,
        expected_items: int = 1000,
        false_positive_rate: float = 0.01,
        hash_size: int = 16,
    ):
        self.bloom = BloomFilter(expected_items, false_positive_rate)
        self.hash_size = hash_size
        self._exact_store: dict[str, str] = {}
        self.stats = {
            "bloom_negative": 0,
            "bloom_positive": 0,
            "exact_match": 0,
            "false_positive": 0,
        }

    def fingerprint(self, image: Image.Image) -> str:
        """Return a perceptual hash for the given image."""
        return simple_phash(image, size=self.hash_size)

    def add(self, image: Image.Image, name: str) -> str:
        """Register an image as seen. Returns its fingerprint."""
        fp = self.fingerprint(image)
        self.bloom.add(fp)
        self._exact_store[fp] = name
        return fp

    def query(self, image: Image.Image) -> tuple[bool, str | None]:
        """Check whether an image has likely been seen before.

        Returns
        -------
        is_possible_duplicate:
            ``True`` if the Bloom filter reports the fingerprint as possibly
            present.
        exact_name:
            The name of the previously seen image if the fingerprint matches
            exactly; otherwise ``None`` (including false positives).
        """
        fp = self.fingerprint(image)

        if fp not in self.bloom:
            self.stats["bloom_negative"] += 1
            return False, None

        self.stats["bloom_positive"] += 1
        exact_name = self._exact_store.get(fp)
        if exact_name is not None:
            self.stats["exact_match"] += 1
        else:
            self.stats["false_positive"] += 1
        return True, exact_name

    def print_stats(self) -> None:
        print("\n========== Image dedup statistics ==========")
        print(f"Bloom filter negative (definitely new): {self.stats['bloom_negative']}")
        print(f"Bloom filter positive (check exact store): {self.stats['bloom_positive']}")
        print(f"  -> exact matches: {self.stats['exact_match']}")
        print(f"  -> false positives: {self.stats['false_positive']}")
        print(f"Total fingerprints stored: {len(self._exact_store)}")
        print(f"Bloom filter memory: {self.bloom.memory_usage_bytes()} bytes")
        print("============================================\n")


def generate_test_image(seed: int, size: tuple[int, int] = (400, 300)) -> Image.Image:
    """Create a simple synthetic image with deterministic shapes."""
    rng = random.Random(seed)
    image = Image.new(
        "RGB", size, color=(rng.randint(180, 255), rng.randint(180, 255), rng.randint(180, 255))
    )
    draw = ImageDraw.Draw(image)

    for _ in range(rng.randint(3, 6)):
        x0, y0 = rng.randint(0, size[0] // 2), rng.randint(0, size[1] // 2)
        x1, y1 = x0 + rng.randint(50, 150), y0 + rng.randint(50, 150)
        color = (rng.randint(0, 200), rng.randint(0, 200), rng.randint(0, 200))
        shape = rng.choice(["ellipse", "rectangle"])
        if shape == "ellipse":
            draw.ellipse([x0, y0, x1, y1], fill=color)
        else:
            draw.rectangle([x0, y0, x1, y1], fill=color)

    return image


def transform_image(image: Image.Image) -> Image.Image:
    """Apply a benign transformation: slight resize and JPEG re-encode."""
    w, h = image.size
    smaller = image.resize((w // 2, h // 2), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    smaller.save(buffer, format="JPEG", quality=85)
    buffer.seek(0)
    return Image.open(buffer)


def demo() -> None:
    dedup = ImageFingerprintDedup(expected_items=100, false_positive_rate=0.05, hash_size=16)

    print("=== Generate base images and register them ===\n")
    base_images = {}
    for i in range(5):
        name = f"image_{i}.jpg"
        img = generate_test_image(seed=i * 100)
        fp = dedup.add(img, name)
        base_images[name] = img
        print(f"Registered {name} -> fingerprint {fp[:16]}...")

    print("\n=== Query exact base images (should all match) ===\n")
    for name, img in base_images.items():
        is_dup, match = dedup.query(img)
        print(f"{name}: {'duplicate' if is_dup else 'new'}, exact match={match}")

    print("\n=== Query transformed versions (resized + re-encoded, should still match) ===\n")
    for name, img in base_images.items():
        transformed = transform_image(img)
        is_dup, match = dedup.query(transformed)
        print(f"transformed {name}: {'duplicate' if is_dup else 'new'}, exact match={match}")

    print("\n=== Query brand-new images (should report 'new') ===\n")
    for i in range(3):
        new_name = f"new_image_{i}.jpg"
        img = generate_test_image(seed=10_000 + i)
        is_dup, match = dedup.query(img)
        print(
            f"{new_name}: {'duplicate (possible false positive!)' if is_dup else 'new'}, exact match={match}"
        )

    dedup.print_stats()

    # Optional: save example images for inspection
    output_dir = Path(__file__).with_suffix("").name + "_outputs"
    out = Path(output_dir)
    out.mkdir(exist_ok=True)
    for name, img in base_images.items():
        img.save(out / name, quality=90)
    print(f"Example base images saved to: {out.resolve()}")


if __name__ == "__main__":
    demo()
