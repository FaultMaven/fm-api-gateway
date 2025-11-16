"""fm-auth-service authentication provider implementation"""

import time
import logging
from typing import Dict, Any, Optional
import httpx
from jose import jwt, jwk
from jose.exceptions import JWTError, ExpiredSignatureError
from jose.backends import RSAKey

from ..core.auth_provider import IAuthProvider
from ..core.user_context import UserContext

logger = logging.getLogger(__name__)


class FMAuthProvider(IAuthProvider):
    """
    Authentication provider for fm-auth-service.

    Features:
    - RS256 JWT signature validation using JWK
    - JWK caching (5 minute TTL)
    - Token expiration validation
    - Issuer and audience validation
    """

    def __init__(self, service_url: str, cache_ttl: int = 300):
        """
        Initialize fm-auth-service provider.

        Args:
            service_url: Base URL of fm-auth-service (e.g., http://127.0.0.1:8001)
            cache_ttl: JWK cache TTL in seconds (default: 300 = 5 minutes)
        """
        self.service_url = service_url.rstrip("/")
        self.jwks_url = f"{self.service_url}/.well-known/jwks.json"
        self.cache_ttl = cache_ttl
        self._cached_key = None
        self._cache_time = 0

        logger.info(
            f"Initialized FMAuthProvider with JWKS URL: {self.jwks_url} "
            f"(cache TTL: {cache_ttl}s)"
        )

    async def validate_token(self, token: str) -> UserContext:
        """
        Validate JWT token from fm-auth-service and extract user context.

        Steps:
        1. Fetch JWK from fm-auth-service (cached)
        2. Verify RS256 signature
        3. Validate expiration, issuer, audience
        4. Extract user context from claims

        Args:
            token: JWT token string (without "Bearer " prefix)

        Returns:
            UserContext with user_id, email, roles, email_verified

        Raises:
            ValueError: If token is invalid, expired, or signature verification fails
        """
        try:
            # Get public key (with caching)
            public_key = self._get_public_key()

            # Decode and validate token using python-jose
            # Note: fm-auth-service issues tokens with specific iss and aud
            claims = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience="faultmaven-api",
                issuer="https://auth.faultmaven.ai",
            )

            # Extract user context
            user_context = UserContext(
                user_id=claims["sub"],
                email=claims.get("email", ""),
                roles=claims.get("roles", []),
                email_verified=claims.get("email_verified", False),
            )

            logger.info(
                f"Successfully validated token for user {user_context.user_id} "
                f"via fm-auth-service"
            )

            return user_context

        except ExpiredSignatureError:
            logger.warning("Token validation failed: Token has expired")
            raise ValueError("Token has expired")

        except JWTError as e:
            logger.warning(f"Token validation failed: {str(e)}")
            raise ValueError(f"Invalid token: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error during token validation: {str(e)}")
            raise ValueError(f"Token validation error: {str(e)}")

    def get_provider_name(self) -> str:
        """Return the name of this authentication provider"""
        return "fm-auth-service"

    def _get_public_key(self) -> str:
        """
        Fetch public key from JWKS endpoint with caching.

        Returns:
            Public key in PEM format

        Raises:
            ValueError: If JWKS endpoint is unreachable or invalid
        """
        # Check cache
        current_time = time.time()
        if self._cached_key and (current_time - self._cache_time) < self.cache_ttl:
            return self._cached_key

        # Fetch JWKS
        try:
            response = httpx.get(self.jwks_url, timeout=5.0)
            response.raise_for_status()
            jwks_data = response.json()

            if not jwks_data.get("keys"):
                raise ValueError("No signing keys found in JWKS endpoint")

            # Get first key (fm-auth-service only has one key)
            jwk_data = jwks_data["keys"][0]

            # Convert JWK to PEM format using python-jose
            from jose.backends.cryptography_backend import CryptographyRSAKey

            key_obj = jwk.construct(jwk_data, algorithm="RS256")
            public_key_pem = key_obj.to_pem().decode("utf-8")

            # Cache the key
            self._cached_key = public_key_pem
            self._cache_time = current_time

            logger.debug(f"Fetched and cached public key from {self.jwks_url}")

            return public_key_pem

        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch JWKS from {self.jwks_url}: {str(e)}")
            raise ValueError(f"Cannot fetch JWKS: {str(e)}")

        except Exception as e:
            logger.error(f"Error processing JWKS: {str(e)}")
            raise ValueError(f"Invalid JWKS format: {str(e)}")
