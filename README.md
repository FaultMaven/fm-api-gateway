# fm-api-gateway

**FaultMaven API Gateway** - Hybrid Gateway + Auth Adapter Pattern

## Overview

The `fm-api-gateway` is FaultMaven's central authentication and routing layer that implements a pluggable authentication system supporting multiple auth providers:

- **fm-auth-service** (open-source, self-hosted)
- **Supabase** (enterprise SaaS, stub for future)
- **Auth0** (enterprise SaaS, not yet implemented)

## Architecture

```
Client → NGINX Ingress → fm-api-gateway → Microservices
                            ↓
                    [Auth Provider]
                    - fm-auth-service
                    - Supabase
                    - Auth0
```

### Core Features

1. **JWT Validation**: RS256 signature verification using JWK
2. **User Context Extraction**: Extract user_id, email, roles from tokens
3. **Header Injection**: Add validated `X-User-*` headers for downstream services
4. **Header Stripping**: Prevent client header injection attacks
5. **Service Routing**: Proxy requests to appropriate microservices
6. **Provider Switching**: Change auth providers via configuration only

## Quick Start

### 1. Install Dependencies

```bash
cd fm-api-gateway
pip install -e .
```

### 2. Configure Environment

Edit `.env`:

```bash
PRIMARY_AUTH_PROVIDER=fm-auth-service
FM_AUTH_SERVICE_URL=http://127.0.0.1:8001
GATEWAY_PORT=8080
```

### 3. Start Gateway

```bash
# Using uvicorn directly
uvicorn gateway.main:app --host 0.0.0.0 --port 8080 --reload

# Or using Python module
python -m gateway.main
```

Gateway will be available at: `http://localhost:8080`

### 4. Test Health Check

```bash
curl http://localhost:8080/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "fm-api-gateway",
  "version": "1.0.0"
}
```

## Testing with fm-auth-service

### Step 1: Register User (via Gateway)

```bash
curl -X POST http://localhost:8080/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "test@example.com",
    "password": "secure_password",
    "email": "test@example.com"
  }'
```

Response:
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

### Step 2: Login (via Gateway)

```bash
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "test@example.com",
    "password": "secure_password"
  }'
```

### Step 3: Get User Info (with JWT validation)

```bash
# Save token from login response
TOKEN="eyJhbGc..."

curl http://localhost:8080/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

**What Happens**:
1. Gateway extracts token from `Authorization` header
2. Validates JWT signature using fm-auth-service JWK
3. Strips any client-provided `X-User-*` headers
4. Adds validated headers:
   - `X-User-ID: <user_id>`
   - `X-User-Email: <email>`
   - `X-User-Roles: ["user"]`
5. Proxies request to fm-auth-service with validated headers
6. Returns user info

### Step 4: Verify Header Injection (Security Test)

Try sending forged headers:

```bash
curl http://localhost:8080/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-User-ID: fake-admin-id" \
  -H "X-User-Email: admin@example.com"
```

**Expected Behavior**:
- Gateway logs warning about header injection attempt
- Strips forged headers
- Adds validated headers from JWT
- Backend receives correct user info

## Project Structure

```
fm-api-gateway/
├── src/gateway/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py            # Environment configuration
│   ├── core/
│   │   ├── __init__.py
│   │   ├── auth_provider.py       # IAuthProvider interface
│   │   └── user_context.py        # UserContext dataclass
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── fm_auth_provider.py    # fm-auth-service provider
│   │   └── supabase_provider.py   # Supabase stub
│   └── api/
│       ├── __init__.py
│       ├── middleware.py          # JWT validation middleware
│       └── routes.py              # Health + proxy routes
├── pyproject.toml
├── .env
├── Dockerfile
└── README.md
```

## Key Components

### 1. IAuthProvider Interface

All auth providers implement this interface:

```python
class IAuthProvider(ABC):
    async def validate_token(self, token: str) -> UserContext:
        """Validate JWT and extract user context"""
        pass

    def get_provider_name(self) -> str:
        """Return provider name"""
        pass
```

### 2. UserContext Data Model

```python
@dataclass
class UserContext:
    user_id: str
    email: str
    roles: List[str]
    email_verified: bool

    def to_headers(self) -> dict[str, str]:
        """Convert to X-User-* headers"""
        return {
            "X-User-ID": self.user_id,
            "X-User-Email": self.email,
            "X-User-Roles": json.dumps(self.roles),
            "X-Email-Verified": str(self.email_verified).lower(),
        }
```

### 3. AuthMiddleware

- Extracts JWT from `Authorization: Bearer <token>`
- Validates token using configured provider
- Strips client `X-User-*` headers (security!)
- Adds validated headers
- Allows public access to `/health` and `/api/v1/auth/*`

### 4. FMAuthProvider

- Fetches JWK from fm-auth-service
- Validates RS256 JWT signatures
- Caches JWK for 5 minutes
- Handles token expiration and errors

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PRIMARY_AUTH_PROVIDER` | `fm-auth-service` | Auth provider to use |
| `FM_AUTH_SERVICE_URL` | `http://127.0.0.1:8001` | fm-auth-service URL |
| `FM_SESSION_SERVICE_URL` | `http://127.0.0.1:8002` | fm-session-service URL |
| `FM_CASE_SERVICE_URL` | `http://127.0.0.1:8003` | fm-case-service URL |
| `GATEWAY_HOST` | `0.0.0.0` | Gateway bind host |
| `GATEWAY_PORT` | `8080` | Gateway bind port |
| `CORS_ORIGINS` | `http://localhost:3000,...` | Allowed CORS origins |
| `JWK_CACHE_TTL` | `300` | JWK cache TTL (seconds) |
| `LOG_LEVEL` | `INFO` | Logging level |

### Switching Auth Providers

**Development** (fm-auth-service):
```bash
PRIMARY_AUTH_PROVIDER=fm-auth-service
```

**Production** (Supabase - when implemented):
```bash
PRIMARY_AUTH_PROVIDER=supabase
SUPABASE_PROJECT_ID=your-project-id
SUPABASE_JWT_SECRET=your-jwt-secret
```

## Service Routing

Current routes (configured in `main.py`):

| Path | Backend | Status |
|------|---------|--------|
| `/api/v1/auth/*` | fm-auth-service:8001 | ✅ Working |
| `/api/v1/session/*` | fm-session-service:8002 | ⚠️ Stub (503) |
| `/api/v1/cases/*` | fm-case-service:8003 | ⚠️ Stub (503) |
| `/health` | Gateway itself | ✅ Working |

## Security Features

### 1. Header Injection Prevention

**Attack**: Client sends forged `X-User-ID` header

**Defense**: Middleware strips ALL client `X-User-*` headers before validation

### 2. JWT Signature Validation

**Attack**: Client sends tampered JWT

**Defense**: RS256 signature verification using JWK from auth service

### 3. Token Expiration

**Attack**: Client uses expired token

**Defense**: JWT library validates `exp` claim automatically

### 4. Public Endpoint Bypass

**Attack**: Try to access protected endpoints without token

**Defense**: Middleware returns 401 for missing/invalid tokens (except `/health` and `/api/v1/auth/*`)

## Docker Deployment

### Build Image

```bash
docker build -t fm-api-gateway:latest .
```

### Run Container

```bash
docker run -d \
  --name fm-api-gateway \
  -p 8080:8080 \
  --env-file .env \
  fm-api-gateway:latest
```

## Development

### Run with Hot Reload

```bash
uvicorn gateway.main:app --host 0.0.0.0 --port 8080 --reload
```

### Debug Logging

```bash
LOG_LEVEL=DEBUG python -m gateway.main
```

### Add New Auth Provider

1. Create provider class implementing `IAuthProvider`
2. Add to `infrastructure/` directory
3. Update `_create_auth_provider()` in `main.py`
4. Add environment variables to `.env`

Example:
```python
# infrastructure/auth0_provider.py
class Auth0Provider(IAuthProvider):
    async def validate_token(self, token: str) -> UserContext:
        # Implement Auth0 JWT validation
        pass

    def get_provider_name(self) -> str:
        return "auth0"
```

## Troubleshooting

### Gateway Returns 401 for Valid Token

**Check**:
1. Is fm-auth-service running? (`curl http://127.0.0.1:8001/health`)
2. Is JWK endpoint accessible? (`curl http://127.0.0.1:8001/.well-known/jwks.json`)
3. Check gateway logs for validation errors

### Backend Service Unavailable (503)

**Reason**: Service is not yet implemented or not running

**Solution**: Start the backend service or update service URL in `.env`

### CORS Errors

**Solution**: Add your frontend origin to `CORS_ORIGINS` in `.env`

```bash
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

## Next Steps

1. ✅ **Phase 1 Complete**: Gateway validates JWT from fm-auth-service
2. 🚧 **Phase 2**: Implement fm-session-service and fm-case-service
3. 🚧 **Phase 3**: Add Supabase provider implementation
4. 🚧 **Phase 4**: Add rate limiting and advanced security
5. 🚧 **Phase 5**: Kubernetes deployment with Ingress

## License

Part of FaultMaven - AI-Powered Troubleshooting Copilot
