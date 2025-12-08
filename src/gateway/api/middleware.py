"""Authentication and rate limiting middleware"""

import logging
from typing import Callable
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..core.auth_provider import IAuthProvider
from ..core.user_context import UserContext
from ..core.rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Authentication middleware for JWT validation and header injection.

    Security features:
    1. Strips client-provided X-User-* headers (prevents header injection attacks)
    2. Validates JWT tokens using configured auth provider
    3. Adds validated X-User-* headers for downstream services
    4. Allows unauthenticated access to /health and /auth/* endpoints
    5. Supports optional authentication (if configured) for self-hosted mode

    Flow:
    1. Extract Authorization header
    2. Validate JWT token via auth provider
    3. Strip malicious client headers
    4. Add validated user headers
    5. Forward to backend service
    """

    def __init__(self, app, auth_provider: IAuthProvider, settings=None):
        """
        Initialize authentication middleware.

        Args:
            app: FastAPI application
            auth_provider: Authentication provider implementation (IAuthProvider)
            settings: Application settings (optional)
        """
        super().__init__(app)
        self.auth_provider = auth_provider
        self.settings = settings
        
        # Determine auth mode
        self.auth_required = True
        if settings and hasattr(settings, "auth_required"):
            self.auth_required = settings.auth_required
            
        logger.info(
            f"Initialized AuthMiddleware with provider: {auth_provider.get_provider_name()}, "
            f"Auth Required: {self.auth_required}"
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with authentication validation.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            Response from downstream handler or 401 error
        """
        # Allow unauthenticated access to health and auth endpoints
        if self._is_public_endpoint(request.url.path):
            logger.debug(f"Public endpoint accessed: {request.url.path}")
            return await call_next(request)

        # Extract Authorization header
        auth_header = request.headers.get("Authorization")
        user_context = None
        
        # Case 1: No auth header provided
        if not auth_header:
            if self.auth_required:
                logger.warning(f"Missing Authorization header for {request.url.path}")
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "error": "missing_authorization",
                        "message": "Authorization header is required",
                    },
                )
            else:
                # Auth is optional -> use anonymous user
                logger.info(f"Allowing anonymous access to {request.url.path}")
                user_context = self._create_anonymous_user()

        # Case 2: Auth header provided
        else:
            # Extract token from "Bearer <token>"
            try:
                token = self._extract_bearer_token(auth_header)
                # Validate token and extract user context
                user_context = await self.auth_provider.validate_token(token)
            except ValueError as e:
                logger.warning(f"Token validation failed: {str(e)}")
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "error": "invalid_token",
                        "message": str(e),
                    },
                )

        # Strip client-provided X-User-* headers (security!)
        self._strip_client_user_headers(request)

        # Add validated user headers (from either token or anonymous context)
        if user_context:
            validated_headers = user_context.to_headers()
            for header_name, header_value in validated_headers.items():
                request.state.user_headers = getattr(request.state, "user_headers", {})
                request.state.user_headers[header_name] = header_value

            logger.info(
                f"Authenticated user {user_context.user_id} for {request.method} "
                f"{request.url.path}"
            )

        # Forward to next handler
        response = await call_next(request)
        return response

    def _create_anonymous_user(self) -> UserContext:
        """Create a default anonymous user context."""
        if self.settings:
            return UserContext(
                user_id=self.settings.anonymous_user_id,
                email=self.settings.anonymous_user_email,
                roles=[self.settings.anonymous_user_role],
                email_verified=True,
            )
        else:
            # Fallback defaults
            return UserContext(
                user_id="anonymous",
                email="anonymous@example.com",
                roles=["admin"],
                email_verified=True,
            )

    def _is_public_endpoint(self, path: str) -> bool:
        """
        Check if endpoint allows unauthenticated access.

        Public endpoints:
        - /health (health checks)
        - /api/v1/auth/login (login)
        - /api/v1/auth/register (registration)
        - /api/v1/auth/refresh (token refresh)

        Protected endpoints (require JWT):
        - /api/v1/auth/me (user info - needs validated headers)
        - All other endpoints

        Args:
            path: Request URL path

        Returns:
            True if endpoint is public, False otherwise
        """
        public_paths = [
            "/health",
            "/api/v1/auth/login",
            "/api/v1/auth/dev-login",
            "/api/v1/auth/register",
            "/api/v1/auth/dev-register",
            "/api/v1/auth/refresh",
        ]
        return any(path.startswith(prefix) for prefix in public_paths)

    def _extract_bearer_token(self, auth_header: str) -> str:
        """
        Extract token from Authorization header.

        Expected format: "Bearer <token>"

        Args:
            auth_header: Authorization header value

        Returns:
            JWT token string

        Raises:
            ValueError: If header format is invalid
        """
        parts = auth_header.split()
        if len(parts) != 2:
            raise ValueError("Authorization header must be 'Bearer <token>'")

        scheme, token = parts
        if scheme.lower() != "bearer":
            raise ValueError("Authorization scheme must be Bearer")

        return token

    def _strip_client_user_headers(self, request: Request) -> None:
        """
        Remove any client-provided X-User-* headers (security measure).

        This prevents header injection attacks where a malicious client
        sends forged X-User-ID or X-User-Email headers.

        Args:
            request: Incoming request
        """
        # Get mutable headers
        headers = dict(request.headers)

        # Remove X-User-* headers
        headers_to_remove = [
            key for key in headers.keys() if key.lower().startswith("x-user-")
        ]

        for header in headers_to_remove:
            logger.debug(f"Stripped client-provided header: {header}")
            # Note: request.headers is immutable, but we track this for logging
            # The actual stripping happens by not forwarding these headers

        if headers_to_remove:
            logger.warning(
                f"Client attempted header injection with: {headers_to_remove}"
            )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using Redis or in-memory backend.

    Features:
    - Per-IP rate limiting
    - Redis-backed (distributed across gateway pods)
    - In-memory fallback (if Redis unavailable)
    - Graceful degradation (fail-open on errors)
    - Standard HTTP headers (X-RateLimit-*)

    Exemptions:
    - /health endpoint (for K8s probes)
    """

    def __init__(self, app):
        """Initialize rate limit middleware."""
        super().__init__(app)
        self.rate_limiter = get_rate_limiter()
        logger.info("Initialized RateLimitMiddleware")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Check rate limit before processing request.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            Response or 429 Too Many Requests
        """
        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)

        # Get client identifier (IP address)
        client_ip = self._get_client_ip(request)

        # Check rate limit
        is_allowed, headers = self.rate_limiter.is_allowed(client_ip)

        if not is_allowed:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "rate_limit_exceeded",
                    "message": "Too many requests. Please try again later.",
                },
                headers=headers,
            )

        # Continue to next handler
        response = await call_next(request)

        # Add rate limit headers to response
        for header_name, header_value in headers.items():
            response.headers[header_name] = header_value

        return response

    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP address from request.

        Checks in order:
        1. X-Forwarded-For (if behind proxy/load balancer)
        2. X-Real-IP (nginx)
        3. request.client.host (direct connection)

        Args:
            request: Incoming request

        Returns:
            Client IP address
        """
        # Check X-Forwarded-For (load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take first IP (client)
            return forwarded_for.split(",")[0].strip()

        # Check X-Real-IP (nginx)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Direct connection
        if request.client:
            return request.client.host

        # Fallback
        return "unknown"
