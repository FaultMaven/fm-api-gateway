"""Authentication provider interface for pluggable auth backends"""

from abc import ABC, abstractmethod
from .user_context import UserContext


class IAuthProvider(ABC):
    """
    Interface for authentication providers.

    Implementations must:
    1. Validate JWT tokens from their respective auth services
    2. Extract user context from validated tokens
    3. Handle token expiration and invalid signatures
    """

    @abstractmethod
    async def validate_token(self, token: str) -> UserContext:
        """
        Validate JWT token and extract user context.

        Args:
            token: JWT token string (without "Bearer " prefix)

        Returns:
            UserContext with user_id, email, roles, email_verified

        Raises:
            ValueError: If token is invalid, expired, or signature verification fails
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the name of this authentication provider"""
        pass
