"""Aggregated Health Checker for Kubernetes Readiness Probes.

Provides deep health checks that validate:
- Redis connectivity (for rate limiting and distributed state)
- Circuit breaker states (backend service health)
- Service registry initialization

This ensures Kubernetes only routes traffic to Gateway pods that can
successfully handle requests end-to-end.
"""

import logging
from typing import Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum

from ..infrastructure.redis_client import get_redis_client
from .circuit_breaker import get_circuit_breaker, CircuitState

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Overall health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    """Health status for a single component."""
    name: str
    status: HealthStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AggregatedHealth:
    """Aggregated health check result."""
    status: HealthStatus
    components: List[ComponentHealth]
    ready: bool  # Kubernetes readiness
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "status": self.status.value,
            "ready": self.ready,
            "timestamp": self.timestamp,
            "components": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                    "details": c.details,
                }
                for c in self.components
            ],
        }


class HealthChecker:
    """
    Aggregated health checker for deep K8s readiness probes.

    Checks:
    1. Redis connectivity (critical for rate limiting)
    2. Circuit breaker states (backend service health)
    3. Service registry (deployment mode detection)

    Usage:
        checker = HealthChecker()
        health = await checker.check_readiness()

        if health.ready:
            # Gateway is ready to handle traffic
        else:
            # K8s should remove pod from load balancer
    """

    def __init__(self):
        """Initialize health checker with dependencies."""
        self.redis_client = get_redis_client()
        self.circuit_breaker = get_circuit_breaker()

    async def check_liveness(self) -> AggregatedHealth:
        """
        Liveness probe - check if Gateway process is alive.

        This is a lightweight check that only verifies the Gateway
        process itself is running. Used by Kubernetes to restart
        completely broken pods.

        Returns:
            AggregatedHealth with liveness status
        """
        from datetime import datetime

        # If we can execute this code, the process is alive
        return AggregatedHealth(
            status=HealthStatus.HEALTHY,
            ready=True,
            timestamp=datetime.utcnow().isoformat() + "Z",
            components=[
                ComponentHealth(
                    name="gateway_process",
                    status=HealthStatus.HEALTHY,
                    message="Gateway process is running",
                )
            ],
        )

    async def check_readiness(self) -> AggregatedHealth:
        """
        Readiness probe - check if Gateway can handle traffic.

        This performs deep validation to ensure the Gateway can
        successfully process requests end-to-end. K8s uses this
        to determine if traffic should be routed to this pod.

        Checks:
        1. Redis connectivity (for rate limiting)
        2. Circuit breaker states (any services in OPEN state?)
        3. Service registry (deployment mode configured?)

        Returns:
            AggregatedHealth with readiness status
        """
        from datetime import datetime

        components: List[ComponentHealth] = []

        # Check 1: Redis connectivity
        redis_health = await self._check_redis()
        components.append(redis_health)

        # Check 2: Circuit breaker states
        circuit_health = await self._check_circuit_breakers()
        components.append(circuit_health)

        # Check 3: Service registry
        registry_health = await self._check_service_registry()
        components.append(registry_health)

        # Determine overall status
        overall_status, ready = self._aggregate_status(components)

        return AggregatedHealth(
            status=overall_status,
            ready=ready,
            timestamp=datetime.utcnow().isoformat() + "Z",
            components=components,
        )

    async def _check_redis(self) -> ComponentHealth:
        """Check Redis connectivity."""
        if not self.redis_client.is_available():
            # Redis not configured - degraded but not critical
            # Rate limiting will use in-memory fallback
            return ComponentHealth(
                name="redis",
                status=HealthStatus.DEGRADED,
                message="Redis not available (rate limiting degraded to in-memory)",
                details={"available": False, "impact": "Rate limiting is per-pod only"},
            )

        # Try to ping Redis
        try:
            client = self.redis_client.client
            if client:
                client.ping()
                return ComponentHealth(
                    name="redis",
                    status=HealthStatus.HEALTHY,
                    message="Redis is responsive",
                    details={"available": True, "mode": "standalone or sentinel"},
                )
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return ComponentHealth(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                message=f"Redis ping failed: {str(e)}",
                details={"available": False, "error": str(e)},
            )

        return ComponentHealth(
            name="redis",
            status=HealthStatus.DEGRADED,
            message="Redis client not initialized",
            details={"available": False},
        )

    async def _check_circuit_breakers(self) -> ComponentHealth:
        """Check circuit breaker states for all backend services."""
        if not self.circuit_breaker.enabled:
            return ComponentHealth(
                name="circuit_breakers",
                status=HealthStatus.HEALTHY,
                message="Circuit breakers disabled",
                details={"enabled": False},
            )

        # Known backend services
        services = [
            "fm-auth-service",
            "fm-session-service",
            "fm-case-service",
            "fm-evidence-service",
            "fm-knowledge-service",
            "fm-agent-service",
        ]

        open_circuits = []
        degraded_circuits = []

        for service in services:
            state = self.circuit_breaker.get_state(service)
            if state == CircuitState.OPEN:
                open_circuits.append(service)
            elif state == CircuitState.HALF_OPEN:
                degraded_circuits.append(service)

        # Determine status
        if open_circuits:
            # Critical: Some services completely unavailable
            return ComponentHealth(
                name="circuit_breakers",
                status=HealthStatus.DEGRADED,
                message=f"{len(open_circuits)} service(s) unavailable",
                details={
                    "open_circuits": open_circuits,
                    "half_open_circuits": degraded_circuits,
                    "total_services": len(services),
                },
            )
        elif degraded_circuits:
            # Warning: Some services testing recovery
            return ComponentHealth(
                name="circuit_breakers",
                status=HealthStatus.DEGRADED,
                message=f"{len(degraded_circuits)} service(s) testing recovery",
                details={
                    "open_circuits": open_circuits,
                    "half_open_circuits": degraded_circuits,
                    "total_services": len(services),
                },
            )
        else:
            # All circuits closed - healthy
            return ComponentHealth(
                name="circuit_breakers",
                status=HealthStatus.HEALTHY,
                message="All services available",
                details={
                    "open_circuits": [],
                    "half_open_circuits": [],
                    "total_services": len(services),
                },
            )

    async def _check_service_registry(self) -> ComponentHealth:
        """Check service registry initialization."""
        try:
            from fm_core_lib.discovery import get_service_registry

            registry = get_service_registry()

            # Try to get a known service URL
            auth_url = registry.get_url("auth")

            return ComponentHealth(
                name="service_registry",
                status=HealthStatus.HEALTHY,
                message="Service discovery operational",
                details={
                    "deployment_mode": registry.mode.value,
                    "sample_url": auth_url,
                },
            )
        except Exception as e:
            logger.error(f"Service registry health check failed: {e}")
            return ComponentHealth(
                name="service_registry",
                status=HealthStatus.UNHEALTHY,
                message=f"Service registry initialization failed: {str(e)}",
                details={"error": str(e)},
            )

    def _aggregate_status(
        self, components: List[ComponentHealth]
    ) -> tuple[HealthStatus, bool]:
        """
        Aggregate component statuses into overall status and readiness.

        Logic:
        - UNHEALTHY components -> UNHEALTHY, not ready
        - Only DEGRADED -> DEGRADED, ready (can handle traffic)
        - All HEALTHY -> HEALTHY, ready

        Args:
            components: List of component health checks

        Returns:
            Tuple of (overall_status, ready_for_traffic)
        """
        if any(c.status == HealthStatus.UNHEALTHY for c in components):
            # Critical failure - not ready
            return HealthStatus.UNHEALTHY, False

        if any(c.status == HealthStatus.DEGRADED for c in components):
            # Degraded but functional - still ready
            # Gateway can handle traffic with reduced capability
            # (e.g., per-pod rate limiting instead of distributed)
            return HealthStatus.DEGRADED, True

        # All components healthy
        return HealthStatus.HEALTHY, True


# Singleton instance
_health_checker: HealthChecker | None = None


def get_health_checker() -> HealthChecker:
    """Get or create health checker singleton."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker
