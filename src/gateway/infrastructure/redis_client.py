"""Redis client for rate limiting and circuit breakers.

Supports deployment-neutral configuration:
- Standalone Redis (development)
- Redis Sentinel (production HA)
"""

import logging
import os
from typing import Optional
from redis import Redis, Sentinel
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class RedisClient:
    """Deployment-neutral Redis client."""

    def __init__(self):
        self.client: Optional[Redis] = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize Redis client based on environment configuration."""
        mode = os.getenv("REDIS_MODE", "standalone").lower()

        try:
            if mode == "sentinel":
                self._init_sentinel()
            else:
                self._init_standalone()

            # Test connection
            if self.client:
                self.client.ping()
                logger.info(f"✓ Redis client initialized in {mode} mode")
        except RedisError as e:
            logger.warning(
                f"Redis connection failed ({mode} mode): {e}. "
                "Rate limiting will be disabled."
            )
            self.client = None

    def _init_standalone(self) -> None:
        """Initialize standalone Redis client."""
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        password = os.getenv("REDIS_PASSWORD")
        db = int(os.getenv("REDIS_DB", "0"))

        self.client = Redis(
            host=host,
            port=port,
            password=password,
            db=db,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )

    def _init_sentinel(self) -> None:
        """Initialize Redis Sentinel client for HA."""
        sentinel_hosts_str = os.getenv("REDIS_SENTINEL_HOSTS", "localhost:26379")
        master_name = os.getenv("REDIS_MASTER_SET", "mymaster")
        password = os.getenv("REDIS_PASSWORD")
        db = int(os.getenv("REDIS_DB", "0"))

        # Parse sentinel hosts
        sentinel_hosts = [
            tuple(host.strip().split(":"))
            for host in sentinel_hosts_str.split(",")
        ]
        sentinel_hosts = [(host, int(port)) for host, port in sentinel_hosts]

        sentinel = Sentinel(
            sentinel_hosts,
            socket_timeout=5,
            password=password,
        )

        self.client = sentinel.master_for(
            master_name,
            db=db,
            decode_responses=True,
            socket_timeout=5,
        )

    def get(self, key: str) -> Optional[str]:
        """Get value from Redis with error handling."""
        if not self.client:
            return None

        try:
            return self.client.get(key)
        except RedisError as e:
            logger.warning(f"Redis GET error for key {key}: {e}")
            return None

    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """Set value in Redis with error handling."""
        if not self.client:
            return False

        try:
            self.client.set(key, value, ex=ex)
            return True
        except RedisError as e:
            logger.warning(f"Redis SET error for key {key}: {e}")
            return False

    def incr(self, key: str) -> Optional[int]:
        """Increment counter in Redis with error handling."""
        if not self.client:
            return None

        try:
            return self.client.incr(key)
        except RedisError as e:
            logger.warning(f"Redis INCR error for key {key}: {e}")
            return None

    def expire(self, key: str, seconds: int) -> bool:
        """Set expiration on key with error handling."""
        if not self.client:
            return False

        try:
            self.client.expire(key, seconds)
            return True
        except RedisError as e:
            logger.warning(f"Redis EXPIRE error for key {key}: {e}")
            return False

    def is_available(self) -> bool:
        """Check if Redis is available."""
        return self.client is not None


# Singleton instance
_redis_client: Optional[RedisClient] = None


def get_redis_client() -> RedisClient:
    """Get or create Redis client singleton."""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client
