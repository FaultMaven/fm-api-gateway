"""API routes for health checks and service proxying"""

import logging
from typing import Any, Dict
import httpx
from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()


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
    1. Forwards the request to the backend service
    2. Adds validated X-User-* headers from middleware
    3. Preserves original request method, body, and headers
    4. Returns backend response to client

    Args:
        request: Original FastAPI request
        backend_url: Backend service base URL (e.g., http://127.0.0.1:8001)
        path: Request path to append to backend URL

    Returns:
        Response from backend service
    """
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

        # Return backend response
        return Response(
            content=backend_response.content,
            status_code=backend_response.status_code,
            headers=dict(backend_response.headers),
        )

    except httpx.TimeoutException:
        logger.error(f"Backend timeout for {target_url}")
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={
                "error": "backend_timeout",
                "message": "Backend service did not respond in time",
            },
        )

    except httpx.RequestError as e:
        logger.error(f"Backend request error for {target_url}: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "error": "backend_error",
                "message": f"Failed to connect to backend service: {str(e)}",
            },
        )

    except Exception as e:
        logger.error(f"Unexpected error proxying to {target_url}: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "proxy_error",
                "message": f"Internal gateway error: {str(e)}",
            },
        )
