"""Supabase authentication provider (stub implementation for future)"""

import logging
from ..core.auth_provider import IAuthProvider
from ..core.user_context import UserContext

logger = logging.getLogger(__name__)


class SupabaseProvider(IAuthProvider):
    """
    Authentication provider for Supabase (stub implementation).

    This is a placeholder for future Supabase integration.
    When implemented, it will:
    - Validate Supabase JWT tokens using their JWK endpoint
    - Support OAuth providers (Google, GitHub, etc.)
    - Handle Supabase-specific claims structure
    """

    def __init__(self, project_id: str, jwt_secret: str):
        """
        Initialize Supabase provider (stub).

        Args:
            project_id: Supabase project ID
            jwt_secret: Supabase JWT secret
        """
        self.project_id = project_id
        self.jwt_secret = jwt_secret
        self.jwks_url = f"https://{project_id}.supabase.co/.well-known/jwks.json"

        logger.info(
            f"Initialized SupabaseProvider (STUB) for project: {project_id}"
        )

    async def validate_token(self, token: str) -> UserContext:
        """
        Validate Supabase JWT token (stub - not implemented).

        Args:
            token: JWT token string

        Raises:
            NotImplementedError: This provider is not yet implemented
        """
        raise NotImplementedError(
            "Supabase provider is not yet implemented. "
            "Use fm-auth-service for now."
        )

    def get_provider_name(self) -> str:
        """Return the name of this authentication provider"""
        return "supabase"
