"""Shared NVIDIA NIM rate budget.

The free NIM tier caps at ~40 requests/minute across ALL calls — embeddings and
chat LLM combined. A single process-wide token bucket sits in front of every
NVIDIA call so the two never race each other past the cap.

- Embeddings call ``get_rate_limiter().acquire(blocking=True)`` before each API
  request (from a worker thread, so blocking is fine).
- The chat model (ChatNVIDIA) is constructed with ``rate_limiter=`` set to this
  same instance, so both share one bucket.

Refill is steady at ``nvidia_max_rpm / 60`` tokens/second with a small burst
allowance; that keeps the sustained rate safely under the hard 40/min ceiling.
"""

from __future__ import annotations

from functools import lru_cache

from langchain_core.rate_limiters import InMemoryRateLimiter

from app.config import get_settings


@lru_cache
def get_rate_limiter() -> InMemoryRateLimiter:
    settings = get_settings()
    requests_per_second = settings.nvidia_max_rpm / 60.0
    return InMemoryRateLimiter(
        requests_per_second=requests_per_second,
        # Wake often enough to feel responsive without busy-waiting.
        check_every_n_seconds=0.1,
        # Burst ceiling: allow a few back-to-back calls, then throttle to the
        # steady refill rate so a burst can't push total throughput over 40/min.
        max_bucket_size=float(settings.nvidia_burst),
    )
