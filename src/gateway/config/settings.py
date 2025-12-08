"""Gateway configuration using pydantic-settings"""

from typing import Literal, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from fm_core_lib.discovery import get_service_registry, ServiceRegistry


class Settings(BaseSettings):
    """Gateway configuration from environment variables"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Authentication Provider
    primary_auth_provider: Literal["fm-auth-service", "supabase", "auth0"] = Field(
        default="fm-auth-service",
        description="Primary authentication provider to use",
    )

    # Service Discovery Configuration
    deployment_mode: str = Field(
        default="docker",
        description="Deployment mode: 'docker', 'kubernetes', or 'local'",
    )
    k8s_namespace: str = Field(
        default="faultmaven",
        description="Kubernetes namespace (only used when deployment_mode=kubernetes)",
    )

    # Legacy: Manual service URL overrides (deprecated in favor of ServiceRegistry)
    # These are kept for backward compatibility but ServiceRegistry is preferred
    fm_auth_service_url: Optional[str] = Field(
        default=None,
        description="Override URL for fm-auth-service (legacy)",
    )
    fm_session_service_url: Optional[str] = Field(
        default=None,
        description="Override URL for fm-session-service (legacy)",
    )
    fm_case_service_url: Optional[str] = Field(
        default=None,
        description="Override URL for fm-case-service (legacy)",
    )
    fm_evidence_service_url: Optional[str] = Field(
        default=None,
        description="Override URL for fm-evidence-service (legacy)",
    )
    fm_investigation_service_url: Optional[str] = Field(
        default=None,
        description="Override URL for fm-investigation-service (legacy)",
    )
    fm_knowledge_service_url: Optional[str] = Field(
        default=None,
        description="Override URL for fm-knowledge-service (legacy)",
    )
    fm_agent_service_url: Optional[str] = Field(
        default=None,
        description="Override URL for fm-agent-service (legacy)",
    )

    # Service Registry instance (lazy-initialized)
    _service_registry: Optional[ServiceRegistry] = None

    def get_service_url(self, service_name: str) -> str:
        """Get service URL using ServiceRegistry or legacy override.

        Args:
            service_name: Service name (e.g., "auth", "session", "case")

        Returns:
            Full service URL

        Example:
            >>> settings = Settings()
            >>> settings.get_service_url("auth")
            'http://fm-auth-service:8000'  # Docker mode
        """
        # Check for legacy manual override first
        override_attr = f"fm_{service_name}_service_url"
        if hasattr(self, override_attr):
            override_url = getattr(self, override_attr)
            if override_url:
                return override_url

        # Use ServiceRegistry for deployment-neutral URL resolution
        if self._service_registry is None:
            self._service_registry = get_service_registry()

        return self._service_registry.get_url(service_name)

    # Gateway Configuration
    gateway_host: str = Field(
        default="0.0.0.0",
        description="Gateway bind host",
    )
    gateway_port: int = Field(
        default=8080,
        description="Gateway bind port",
    )

    # CORS Configuration
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:5173,http://localhost:8080",
        description="Comma-separated list of allowed CORS origins",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )

    # JWK Cache Configuration
    jwk_cache_ttl: int = Field(
        default=300,
        description="JWK cache TTL in seconds (5 minutes)",
    )

    # Authentication Configuration
    auth_required: bool = Field(
        default=True,
        description="Whether to enforce authentication. Set to False for self-hosted mode.",
    )
    anonymous_user_id: str = Field(
        default="anonymous_admin",
        description="User ID to use when auth is optional and no token is provided",
    )
    anonymous_user_email: str = Field(
        default="admin@example.com",
        description="Email to use when auth is optional and no token is provided",
    )
    anonymous_user_role: str = Field(
        default="admin",
        description="Role to use when auth is optional and no token is provided",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins into list"""
        return [origin.strip() for origin in self.cors_origins.split(",")]


# Singleton settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create settings singleton"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
