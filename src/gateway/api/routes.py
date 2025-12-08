"""API routes for health checks and service proxying"""

import logging
from typing import Any, Dict
import httpx
from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse

from ..core.circuit_breaker import get_circuit_breaker

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize circuit breaker
circuit_breaker = get_circuit_breaker()


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint.

    Returns:
        Gateway health status
    """
    return {
        "status": "healthy",
        "service": "fm-api-gateway",
        "version": "1.0.0",
    }


async def proxy_request(
    request: Request,
    backend_url: str,
    path: str,
) -> Response:
    """
    Proxy request to backend service with validated user headers.

    This function:
    1. Checks circuit breaker status
    2. Forwards the request to the backend service
    3. Adds validated X-User-* headers from middleware
    4. Preserves original request method, body, and headers
    5. Records success/failure for circuit breaker
    6. Returns backend response to client

    Args:
        request: Original FastAPI request
        backend_url: Backend service base URL (e.g., http://fm-auth-service:8000)
        path: Request path to append to backend URL

    Returns:
        Response from backend service or circuit breaker error
    """
    # Extract service name from backend URL
    service_name = _extract_service_name(backend_url)

    # Check circuit breaker
    if not circuit_breaker.is_call_allowed(service_name):
        logger.error(f"Circuit breaker OPEN for {service_name}, rejecting request")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "service_unavailable",
                "message": f"{service_name} is temporarily unavailable (circuit breaker open)",
            },
        )

    # Build target URL
    target_url = f"{backend_url.rstrip('/')}{path}"

    # Get request body
    body = await request.body()

    # Build headers
    headers = dict(request.headers)

    # Remove hop-by-hop headers
    hop_by_hop_headers = [
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "host",  # Will be set by httpx
    ]
    for header in hop_by_hop_headers:
        headers.pop(header, None)

    # Add validated user headers from middleware
    if hasattr(request.state, "user_headers"):
        headers.update(request.state.user_headers)
        logger.debug(f"Added validated user headers: {request.state.user_headers}")

    # Make request to backend
    try:
        async with httpx.AsyncClient() as client:
            backend_response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                timeout=30.0,
            )

        logger.info(
            f"Proxied {request.method} {path} to {backend_url} "
            f"-> {backend_response.status_code}"
        )

        # Record success/failure for circuit breaker
        if 200 <= backend_response.status_code < 500:
            # 2xx, 3xx, 4xx = success (service is healthy, just client error)
            circuit_breaker.record_success(service_name)
        else:
            # 5xx = service failure
            circuit_breaker.record_failure(service_name)
            logger.warning(
                f"Service {service_name} returned {backend_response.status_code}, "
                f"recording circuit breaker failure"
            )

        # Return backend response
        return Response(
            content=backend_response.content,
            status_code=backend_response.status_code,
            headers=dict(backend_response.headers),
        )

    except httpx.TimeoutException:
        circuit_breaker.record_failure(service_name)
        logger.error(f"Backend timeout for {target_url}")
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={
                "error": "backend_timeout",
                "message": "Backend service did not respond in time",
            },
        )

    except httpx.RequestError as e:
        circuit_breaker.record_failure(service_name)
        logger.error(f"Backend request error for {target_url}: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "error": "backend_error",
                "message": f"Failed to connect to backend service: {str(e)}",
            },
        )

    except Exception as e:
        circuit_breaker.record_failure(service_name)
        logger.error(f"Unexpected error proxying to {target_url}: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "proxy_error",
                "message": f"Internal gateway error: {str(e)}",
            },
        )


def _extract_service_name(backend_url: str) -> str:
    """
    Extract service name from backend URL.

    Examples:
        http://fm-auth-service:8000 -> fm-auth-service
        http://fm-knowledge-service.faultmaven.svc.cluster.local:8003 -> fm-knowledge-service
        http://localhost:8000 -> localhost

    Args:
        backend_url: Backend service URL

    Returns:
        Service name
    """
    # Parse URL to get hostname
    from urllib.parse import urlparse
    parsed = urlparse(backend_url)
    hostname = parsed.hostname or "unknown"

    # Extract service name (first part of hostname)
    service_name = hostname.split(".")[0]
    return service_name
