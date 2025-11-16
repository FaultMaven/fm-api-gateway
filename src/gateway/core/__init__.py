"""Core domain models and interfaces for authentication"""

from .auth_provider import IAuthProvider
from .user_context import UserContext

__all__ = ["IAuthProvider", "UserContext"]
