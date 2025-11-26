"""
FaultMaven API Gateway - Main Application

Implements Hybrid Gateway + Auth Adapter Pattern:
- Pluggable authentication providers (fm-auth-service, Supabase, Auth0)
- JWT validation and user context extraction
- Request routing to microservices
- Header injection prevention and validation
"""

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .core.auth_provider import IAuthProvider
from .infrastructure import FMAuthProvider, SupabaseProvider
from .api.middleware import AuthMiddleware
from .api.routes import router, proxy_request
from .api.openapi_aggregator import OpenAPIAggregator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan manager for startup/shutdown events"""
    # Startup
    settings = get_settings()
    logger.info(f"Starting fm-api-gateway v1.0.0")
    logger.info(f"Primary auth provider: {settings.primary_auth_provider}")
    logger.info(f"Gateway listening on {settings.gateway_host}:{settings.gateway_port}")

    yield

    # Shutdown
    logger.info("Shutting down fm-api-gateway")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.

    Returns:
        Configured FastAPI application
    """
    settings = get_settings()

    # Initialize OpenAPI aggregator
    aggregator = OpenAPIAggregator({
        "auth": settings.fm_auth_service_url,
        "session": settings.fm_session_service_url,
        "case": settings.fm_case_service_url,
        "evidence": settings.fm_evidence_service_url,
        "investigation": settings.fm_investigation_service_url,
        "knowledge": settings.fm_knowledge_service_url,
        "agent": settings.fm_agent_service_url,
    })

    # Create FastAPI app with custom OpenAPI endpoint
    app = FastAPI(
        title="FaultMaven API Gateway",
        description="Hybrid Gateway + Auth Adapter Pattern",
        version="1.0.0",
        lifespan=lifespan,
        # Disable default OpenAPI docs - we'll use aggregated version
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize auth provider based on configuration
    auth_provider = _create_auth_provider(settings)

    # Add authentication middleware
    app.add_middleware(AuthMiddleware, auth_provider=auth_provider, settings=settings)

    # Add custom OpenAPI endpoints
    @app.get("/openapi.json", include_in_schema=False)
    async def get_unified_openapi():
        """Get unified OpenAPI specification from all microservices"""
        return await aggregator.get_unified_spec()

    @app.get("/docs", include_in_schema=False)
    async def get_unified_docs():
        """Swagger UI for unified API documentation"""
        from fastapi.openapi.docs import get_swagger_ui_html
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title="FaultMaven API - Unified Documentation",
        )

    @app.get("/redoc", include_in_schema=False)
    async def get_unified_redoc():
        """ReDoc UI for unified API documentation"""
        from fastapi.openapi.docs import get_redoc_html
        return get_redoc_html(
            openapi_url="/openapi.json",
            title="FaultMaven API - Unified Documentation",
        )

    # Include health check route
    app.include_router(router)

    # Add service proxy routes
    _add_proxy_routes(app, settings)

    return app


def _create_auth_provider(settings) -> IAuthProvider:
    """
    Create authentication provider based on configuration.

    Args:
        settings: Application settings

    Returns:
        Configured IAuthProvider implementation

    Raises:
        ValueError: If provider is not supported
    """
    if settings.primary_auth_provider == "fm-auth-service":
        logger.info("Using fm-auth-service provider")
        return FMAuthProvider(
            service_url=settings.fm_auth_service_url,
            cache_ttl=settings.jwk_cache_ttl,
        )
    elif settings.primary_auth_provider == "supabase":
        logger.warning("Supabase provider is not yet implemented (stub only)")
        return SupabaseProvider(
            project_id="placeholder",
            jwt_secret="placeholder",
        )
    elif settings.primary_auth_provider == "auth0":
        raise NotImplementedError("Auth0 provider is not yet implemented")
    else:
        raise ValueError(
            f"Unsupported auth provider: {settings.primary_auth_provider}"
        )


def _add_proxy_routes(app: FastAPI, settings) -> None:
    """
    Add proxy routes for microservices.

    Routes:
    - /api/v1/auth/* -> fm-auth-service
    - /api/v1/sessions/* -> fm-session-service
    - /api/v1/cases/* -> fm-case-service (stub)

    Args:
        app: FastAPI application
        settings: Application settings
    """

    # Route: /api/v1/auth/* -> fm-auth-service
    @app.api_route(
        "/api/v1/auth/{path:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    )
    async def proxy_auth(request: Request, path: str):
        """Proxy authentication requests to fm-auth-service"""
        return await proxy_request(
            request,
            backend_url=settings.fm_auth_service_url,
            path=f"/api/v1/auth/{path}",
        )

    # Route: /api/v1/sessions/* -> fm-session-service
    @app.api_route(
        "/api/v1/sessions/{path:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    )
    async def proxy_sessions(request: Request, path: str):
        """Proxy session requests to fm-session-service"""
        return await proxy_request(
            request,
            backend_url=settings.fm_session_service_url,
            path=f"/api/v1/sessions/{path}",
        )

    # Route: /api/v1/sessions (no path) -> fm-session-service
    @app.api_route(
        "/api/v1/sessions",
        methods=["GET", "POST", "OPTIONS"],
    )
    async def proxy_sessions_root(request: Request):
        """Proxy session list/create requests to fm-session-service"""
        return await proxy_request(
            request,
            backend_url=settings.fm_session_service_url,
            path="/api/v1/sessions",
        )

    # Route: /api/v1/cases/* -> fm-case-service
    @app.api_route(
        "/api/v1/cases/{path:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    )
    async def proxy_cases(request: Request, path: str):
        """Proxy case requests to fm-case-service"""
        return await proxy_request(
            request,
            backend_url=settings.fm_case_service_url,
            path=f"/api/v1/cases/{path}",
        )

    # Route: /api/v1/cases (no path) -> fm-case-service
    @app.api_route(
        "/api/v1/cases",
        methods=["GET", "POST", "OPTIONS"],
    )
    async def proxy_cases_root(request: Request):
        """Proxy case list/create requests to fm-case-service"""
        return await proxy_request(
            request,
            backend_url=settings.fm_case_service_url,
            path="/api/v1/cases",
        )

    # Route: /api/v1/evidence/* -> fm-evidence-service
    @app.api_route(
        "/api/v1/evidence/{path:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    )
    async def proxy_evidence(request: Request, path: str):
        """Proxy evidence requests to fm-evidence-service"""
        return await proxy_request(
            request,
            backend_url=settings.fm_evidence_service_url,
            path=f"/api/v1/evidence/{path}",
        )

    # Route: /api/v1/evidence (no path) -> fm-evidence-service
    @app.api_route(
        "/api/v1/evidence",
        methods=["GET", "POST", "OPTIONS"],
    )
    async def proxy_evidence_root(request: Request):
        """Proxy evidence list/upload requests to fm-evidence-service"""
        return await proxy_request(
            request,
            backend_url=settings.fm_evidence_service_url,
            path="/api/v1/evidence",
        )

    # Route: /api/v1/hypotheses/* -> fm-investigation-service
    @app.api_route(
        "/api/v1/hypotheses/{path:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    )
    async def proxy_hypotheses(request: Request, path: str):
        """Proxy hypothesis requests to fm-investigation-service"""
        return await proxy_request(
            request,
            backend_url=settings.fm_investigation_service_url,
            path=f"/api/v1/hypotheses/{path}",
        )

    # Route: /api/v1/hypotheses (no path) -> fm-investigation-service
    @app.api_route(
        "/api/v1/hypotheses",
        methods=["GET", "POST", "OPTIONS"],
    )
    async def proxy_hypotheses_root(request: Request):
        """Proxy hypothesis list/create requests to fm-investigation-service"""
        return await proxy_request(
            request,
            backend_url=settings.fm_investigation_service_url,
            path="/api/v1/hypotheses",
        )

    # Route: /api/v1/solutions/* -> fm-investigation-service
    @app.api_route(
        "/api/v1/solutions/{path:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    )
    async def proxy_solutions(request: Request, path: str):
        """Proxy solution requests to fm-investigation-service"""
        return await proxy_request(
            request,
            backend_url=settings.fm_investigation_service_url,
            path=f"/api/v1/solutions/{path}",
        )

    # Route: /api/v1/solutions (no path) -> fm-investigation-service
    @app.api_route(
        "/api/v1/solutions",
        methods=["GET", "POST", "OPTIONS"],
    )
    async def proxy_solutions_root(request: Request):
        """Proxy solution list/create requests to fm-investigation-service"""
        return await proxy_request(
            request,
            backend_url=settings.fm_investigation_service_url,
            path="/api/v1/solutions",
        )

    # Route: /api/v1/knowledge/* -> fm-knowledge-service
    @app.api_route(
        "/api/v1/knowledge/{path:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    )
    async def proxy_knowledge(request: Request, path: str):
        """Proxy knowledge requests to fm-knowledge-service"""
        return await proxy_request(
            request,
            backend_url=settings.fm_knowledge_service_url,
            path=f"/api/v1/knowledge/{path}",
        )

    # Route: /api/v1/knowledge (no path) -> fm-knowledge-service
    @app.api_route(
        "/api/v1/knowledge",
        methods=["GET", "POST", "OPTIONS"],
    )
    async def proxy_knowledge_root(request: Request):
        """Proxy knowledge requests to fm-knowledge-service"""
        return await proxy_request(
            request,
            backend_url=settings.fm_knowledge_service_url,
            path="/api/v1/knowledge",
        )

    # Route: /api/v1/agent/* -> fm-agent-service
    @app.api_route(
        "/api/v1/agent/{path:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    )
    async def proxy_agent(request: Request, path: str):
        """Proxy agent requests to fm-agent-service"""
        return await proxy_request(
            request,
            backend_url=settings.fm_agent_service_url,
            path=f"/api/v1/agent/{path}",
        )

    # Route: /api/v1/agent (no path) -> fm-agent-service
    @app.api_route(
        "/api/v1/agent",
        methods=["GET", "POST", "OPTIONS"],
    )
    async def proxy_agent_root(request: Request):
        """Proxy agent requests to fm-agent-service"""
        return await proxy_request(
            request,
            backend_url=settings.fm_agent_service_url,
            path="/api/v1/agent",
        )

    logger.info("Configured proxy routes for auth, session, cases, evidence, investigation, knowledge, and agent services")


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()

    # Configure logging level from settings
    logging.getLogger().setLevel(settings.log_level)

    uvicorn.run(
        "gateway.main:app",
        host=settings.gateway_host,
        port=settings.gateway_port,
        reload=True,
        log_level=settings.log_level.lower(),
    )
