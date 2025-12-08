"""Deployment-neutral rate limiter.

Supports:
- Redis-backed (distributed, production)
- In-memory (development, fallback)
- Graceful degradation (if Redis fails, allow traffic with warning)
"""

import logging
import time
from typing import Optional
from collections import defaultdict
from threading import Lock

from ..infrastructure.redis_client import get_redis_client

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter with Redis backend."""

    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_size: Optional[int] = None,
        enabled: bool = True,
    ):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests allowed per minute
            burst_size: Maximum burst size (default: 2x rate)
            enabled: Whether rate limiting is enabled
        """
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size or (requests_per_minute * 2)
        self.enabled = enabled

        # Redis client (may be None if Redis unavailable)
        self.redis = get_redis_client()

        # In-memory fallback (per-process, not distributed)
        self._memory_buckets: dict = defaultdict(lambda: {"tokens": self.burst_size, "last_update": time.time()})
        self._lock = Lock()

        logger.info(
            f"Rate limiter initialized: {requests_per_minute} req/min, "
            f"burst={self.burst_size}, "
            f"backend={'Redis' if self.redis.is_available() else 'in-memory'}"
        )

    def is_allowed(self, identifier: str) -> tuple[bool, dict]:
        """
        Check if request is allowed under rate limit.

        Args:
            identifier: Unique identifier (e.g., IP address, user ID)

        Returns:
            Tuple of (is_allowed, headers) where headers contains rate limit info
        """
        if not self.enabled:
            return True, {}

        # Try Redis first
        if self.redis.is_available():
            return self._check_redis(identifier)

        # Fallback to in-memory
        logger.debug("Using in-memory rate limiter (Redis unavailable)")
        return self._check_memory(identifier)

    def _check_redis(self, identifier: str) -> tuple[bool, dict]:
        """Check rate limit using Redis backend."""
        key = f"ratelimit:{identifier}"
        window_key = f"{key}:window"

        try:
            # Get current count
            current = self.redis.incr(key)

            # Set expiration on first request in window
            if current == 1:
                self.redis.expire(key, 60)

            # Calculate remaining
            remaining = max(0, self.requests_per_minute - current)
            is_allowed = current <= self.requests_per_minute

            headers = {
                "X-RateLimit-Limit": str(self.requests_per_minute),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(int(time.time()) + 60),
            }

            if not is_allowed:
                logger.warning(
                    f"Rate limit exceeded for {identifier}: "
                    f"{current}/{self.requests_per_minute} requests"
                )

            return is_allowed, headers

        except Exception as e:
            logger.warning(f"Redis rate limit check failed: {e}. Allowing request.")
            return True, {}  # Fail open

    def _check_memory(self, identifier: str) -> tuple[bool, dict]:
        """Check rate limit using in-memory token bucket."""
        with self._lock:
            bucket = self._memory_buckets[identifier]
            now = time.time()

            # Refill tokens based on time elapsed
            time_elapsed = now - bucket["last_update"]
            tokens_to_add = time_elapsed * (self.requests_per_minute / 60.0)
            bucket["tokens"] = min(self.burst_size, bucket["tokens"] + tokens_to_add)
            bucket["last_update"] = now

            # Check if token available
            if bucket["tokens"] >= 1:
                bucket["tokens"] -= 1
                remaining = int(bucket["tokens"])
                headers = {
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": str(remaining),
                }
                return True, headers
            else:
                logger.warning(
                    f"Rate limit exceeded (in-memory) for {identifier}"
                )
                headers = {
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                }
                return False, headers


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create rate limiter singleton."""
    global _rate_limiter
    if _rate_limiter is None:
        # Read configuration from environment
        import os
        enabled = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
        requests_per_minute = int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "60"))

        _rate_limiter = RateLimiter(
            requests_per_minute=requests_per_minute,
            enabled=enabled,
        )
    return _rate_limiter
