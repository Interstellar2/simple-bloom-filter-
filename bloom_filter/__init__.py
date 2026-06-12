"""
simple-bloom-filter

A simple, dependency-light Bloom Filter implementation in Python.

Provides:
- ``BloomFilter``: standard space-efficient probabilistic set membership.
- ``CountingBloomFilter``: variant supporting deletion via counters.
"""

from .core import BloomFilter
from .counting import CountingBloomFilter

__all__ = ["BloomFilter", "CountingBloomFilter"]
__version__ = "0.1.0"
