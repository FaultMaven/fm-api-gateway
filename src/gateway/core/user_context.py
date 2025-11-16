"""User context data model extracted from JWT tokens"""

from dataclasses import dataclass
from typing import List


@dataclass
class UserContext:
    """User context extracted from validated JWT token"""

    user_id: str
    email: str
    roles: List[str]
    email_verified: bool

    def to_headers(self) -> dict[str, str]:
        """
        Convert user context to HTTP headers for downstream services.

        Returns validated headers that services can trust:
        - X-User-ID: User identifier
        - X-User-Email: User email address
        - X-User-Roles: JSON array of user roles
        - X-Email-Verified: Email verification status
        """
        import json

        return {
            "X-User-ID": self.user_id,
            "X-User-Email": self.email,
            "X-User-Roles": json.dumps(self.roles),
            "X-Email-Verified": str(self.email_verified).lower(),
        }
