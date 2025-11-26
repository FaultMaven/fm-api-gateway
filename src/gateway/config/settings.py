"""Gateway configuration using pydantic-settings"""

from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Service URLs
    fm_auth_service_url: str = Field(
        default="http://127.0.0.1:8001",
        description="URL for fm-auth-service",
    )
    fm_session_service_url: str = Field(
        default="http://127.0.0.1:8002",
        description="URL for fm-session-service",
    )
    fm_case_service_url: str = Field(
        default="http://127.0.0.1:8003",
        description="URL for fm-case-service",
    )
    fm_evidence_service_url: str = Field(
        default="http://127.0.0.1:8004",
        description="URL for fm-evidence-service",
    )
    fm_investigation_service_url: str = Field(
        default="http://127.0.0.1:8005",
        description="URL for fm-investigation-service",
    )
    fm_knowledge_service_url: str = Field(
        default="http://127.0.0.1:8006",
        description="URL for fm-knowledge-service",
    )
    fm_agent_service_url: str = Field(
        default="http://127.0.0.1:8007",
        description="URL for fm-agent-service",
    )

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
