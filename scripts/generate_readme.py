#!/usr/bin/env python3
"""Auto-generate README.md from OpenAPI specification.

This script reads the OpenAPI spec generated from FastAPI and creates
a comprehensive README with endpoint documentation, proxy routes, and statistics.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Any


def load_openapi_spec() -> Dict[str, Any]:
    """Load OpenAPI spec from docs/api/openapi.json"""
    spec_path = Path(__file__).parent.parent / "docs" / "api" / "openapi.json"

    if not spec_path.exists():
        raise FileNotFoundError(
            f"OpenAPI spec not found at {spec_path}. "
            "Run the app to generate it first."
        )

    with open(spec_path, 'r') as f:
        return json.load(f)


def generate_endpoint_table(spec: Dict[str, Any]) -> str:
    """Generate markdown table of Gateway endpoints (non-proxy)"""
    endpoints = []

    for path, methods in spec.get('paths', {}).items():
        # Only include direct Gateway endpoints, not proxy routes
        if not path.startswith('/api/v1/'):
            for method, details in methods.items():
                if method.lower() in ['get', 'post', 'put', 'delete', 'patch']:
                    summary = details.get('summary', path)
                    endpoints.append({
                        'method': method.upper(),
                        'path': path,
                        'summary': summary
                    })

    # Sort endpoints: health first, then by path
    def sort_key(e):
        if e['path'] == '/health':
            return (0, '')
        elif '/health/' in e['path']:
            return (1, e['path'])
        return (2, e['path'])

    endpoints.sort(key=sort_key)

    # Build markdown table
    table = "| Method | Endpoint | Description |\n"
    table += "|--------|----------|-------------|\n"

    for endpoint in endpoints:
        table += f"| {endpoint['method']} | `{endpoint['path']}` | {endpoint['summary']} |\n"

    return table


def generate_proxy_routes_table() -> str:
    """Generate markdown table of proxy routes to microservices"""
    # These are the proxy routes defined in main.py _add_proxy_routes
    proxy_routes = [
        {
            'pattern': '/api/v1/auth/*',
            'service': 'fm-auth-service',
            'port': '8000',
            'description': 'Authentication and authorization'
        },
        {
            'pattern': '/api/v1/sessions/*',
            'service': 'fm-session-service',
            'port': '8001',
            'description': 'Investigation session management'
        },
        {
            'pattern': '/api/v1/cases/*',
            'service': 'fm-case-service',
            'port': '8003',
            'description': 'Case lifecycle management'
        },
        {
            'pattern': '/api/v1/evidence/*',
            'service': 'fm-evidence-service',
            'port': '8004',
            'description': 'Evidence artifact storage'
        },
        {
            'pattern': '/api/v1/hypotheses/*',
            'service': 'fm-investigation-service',
            'port': '8005',
            'description': 'Hypothesis tracking'
        },
        {
            'pattern': '/api/v1/solutions/*',
            'service': 'fm-investigation-service',
            'port': '8005',
            'description': 'Solution management'
        },
        {
            'pattern': '/api/v1/knowledge/*',
            'service': 'fm-knowledge-service',
            'port': '8002',
            'description': 'Knowledge base and recommendations'
        },
        {
            'pattern': '/api/v1/agent/*',
            'service': 'fm-agent-service',
            'port': '8006',
            'description': 'AI agent orchestration'
        },
    ]

    table = "| Route Pattern | Backend Service | Port | Description |\n"
    table += "|---------------|-----------------|------|-------------|\n"

    for route in proxy_routes:
        table += f"| `{route['pattern']}` | {route['service']} | {route['port']} | {route['description']} |\n"

    return table


def extract_response_codes(spec: Dict[str, Any]) -> Dict[str, Set[str]]:
    """Extract unique response codes and their descriptions across all endpoints"""
    response_info = {}

    for path, methods in spec.get('paths', {}).items():
        for method, details in methods.items():
            if method.lower() in ['get', 'post', 'put', 'delete', 'patch']:
                for code, response_details in details.get('responses', {}).items():
                    desc = response_details.get('description', 'No description')
                    if code not in response_info:
                        response_info[code] = set()
                    response_info[code].add(desc)

    return response_info


def generate_response_codes_section(spec: Dict[str, Any]) -> str:
    """Generate response codes documentation"""
    response_info = extract_response_codes(spec)

    if not response_info:
        return ""

    section = "\n## Common Response Codes\n\n"

    # Sort codes numerically
    for code in sorted(response_info.keys(), key=lambda x: int(x)):
        descriptions = list(response_info[code])
        section += f"- **{code}**: {descriptions[0]}\n"

    return section


def count_endpoints(spec: Dict[str, Any]) -> int:
    """Count total number of endpoints"""
    count = 0
    for path, methods in spec.get('paths', {}).items():
        for method in methods.keys():
            if method.lower() in ['get', 'post', 'put', 'delete', 'patch']:
                count += 1
    return count


def main():
    """Generate README.md from OpenAPI specification"""
    print("🚀 Generating README.md from OpenAPI specification...")

    # Load spec
    spec = load_openapi_spec()

    # Extract metadata
    info = spec.get('info', {})
    title = info.get('title', 'fm-api-gateway')
    version = info.get('version', '1.0.0')
    description = info.get('description', 'FaultMaven API Gateway')

    # Generate sections
    endpoint_table = generate_endpoint_table(spec)
    proxy_routes_table = generate_proxy_routes_table()
    response_codes = generate_response_codes_section(spec)
    total_endpoints = count_endpoints(spec)
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')

    # Build README content
    readme_content = f"""# {title}

> **🤖 This README is auto-generated** from code on every commit.
> Last updated: **{timestamp}** | Total endpoints: **{total_endpoints}**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://hub.docker.com/r/faultmaven/fm-api-gateway)
[![Auto-Docs](https://img.shields.io/badge/docs-auto--generated-success.svg)](.github/workflows/generate-docs.yml)

## Overview

**{description}** - Central entry point for all FaultMaven microservices.

The API Gateway implements a **Hybrid Gateway + Auth Adapter Pattern**, providing:

**Core Capabilities:**
- **Pluggable Authentication**: Support for multiple auth providers (fm-auth-service, Supabase, Auth0)
- **JWT Validation**: Automatic token validation and user context extraction
- **Request Proxying**: Intelligent routing to backend microservices
- **Header Injection**: Secure user context propagation via X-User-* headers
- **Circuit Breaking**: Automatic failure detection and service protection
- **Rate Limiting**: Distributed rate limiting via Redis
- **Health Checks**: Kubernetes-ready liveness and readiness probes
- **Unified OpenAPI**: Aggregated API documentation from all services

**Security Model:**
- ✅ JWT validation on every request
- ✅ Automatic user context extraction (user_id, email, roles)
- ✅ Header injection prevention (untrusted X-User-* headers stripped)
- ✅ Circuit breakers protect against cascading failures
- ✅ Rate limiting prevents abuse

## Quick Start

### Using Docker (Recommended)

```bash
docker run -p 8000:8000 \\
  -e PRIMARY_AUTH_PROVIDER=fm-auth-service \\
  -e FM_AUTH_SERVICE_URL=http://fm-auth-service:8000 \\
  faultmaven/fm-api-gateway:latest
```

The gateway will be available at `http://localhost:8000`.

### Using Docker Compose

See [faultmaven-deploy](https://github.com/FaultMaven/faultmaven-deploy) for complete deployment with all FaultMaven services.

### Development Setup

```bash
# Clone repository
git clone https://github.com/FaultMaven/fm-api-gateway.git
cd fm-api-gateway

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate

# Install dependencies
pip install -e .

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Run gateway
uvicorn gateway.main:app --reload --port 8000
```

## Gateway Endpoints

These are the direct Gateway endpoints (health checks, docs, admin):

{endpoint_table}

**OpenAPI Documentation**: See [docs/api/openapi.json](docs/api/openapi.json) or [docs/api/openapi.yaml](docs/api/openapi.yaml) for complete unified API specification.

## Proxy Routes

The Gateway proxies requests to backend microservices:

{proxy_routes_table}

**Example Request Flow:**

```
Client Request: POST /api/v1/sessions
                   ↓
[API Gateway - Authentication & Routing]
  1. Validate JWT token
  2. Extract user context
  3. Add X-User-ID, X-User-Email headers
  4. Check circuit breaker
  5. Proxy to backend
                   ↓
Backend: fm-session-service:8001/api/v1/sessions
                   ↓
Response flows back through gateway to client
```
{response_codes}

## Configuration

Configuration via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `PRIMARY_AUTH_PROVIDER` | Auth provider (fm-auth-service/supabase/auth0) | `fm-auth-service` |
| `GATEWAY_HOST` | Gateway bind host | `0.0.0.0` |
| `GATEWAY_PORT` | Gateway bind port | `8000` |
| `FM_AUTH_SERVICE_URL` | fm-auth-service URL | `http://localhost:8000` |
| `FM_SESSION_SERVICE_URL` | fm-session-service URL | `http://localhost:8001` |
| `FM_KNOWLEDGE_SERVICE_URL` | fm-knowledge-service URL | `http://localhost:8002` |
| `FM_CASE_SERVICE_URL` | fm-case-service URL | `http://localhost:8003` |
| `FM_EVIDENCE_SERVICE_URL` | fm-evidence-service URL | `http://localhost:8004` |
| `FM_INVESTIGATION_SERVICE_URL` | fm-investigation-service URL | `http://localhost:8005` |
| `FM_AGENT_SERVICE_URL` | fm-agent-service URL | `http://localhost:8006` |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | `*` |
| `LOG_LEVEL` | Logging level (DEBUG/INFO/WARNING/ERROR) | `INFO` |
| `REDIS_URL` | Redis URL for rate limiting | `redis://localhost:6379` |
| `RATE_LIMIT_ENABLED` | Enable rate limiting | `true` |
| `RATE_LIMIT_REQUESTS` | Max requests per window | `100` |
| `RATE_LIMIT_WINDOW_SECONDS` | Rate limit window | `60` |
| `CIRCUIT_BREAKER_ENABLED` | Enable circuit breakers | `true` |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | Failures before opening | `5` |
| `CIRCUIT_BREAKER_TIMEOUT_SECONDS` | Circuit open duration | `60` |

Example `.env` file:

```env
PRIMARY_AUTH_PROVIDER=fm-auth-service
GATEWAY_PORT=8000
FM_AUTH_SERVICE_URL=http://fm-auth-service:8000
FM_SESSION_SERVICE_URL=http://fm-session-service:8001
FM_CASE_SERVICE_URL=http://fm-case-service:8003
CORS_ORIGINS=https://app.faultmaven.com,https://admin.faultmaven.com
LOG_LEVEL=INFO
REDIS_URL=redis://redis:6379
```

## Authentication Flow

The Gateway uses pluggable authentication providers:

### fm-auth-service Provider (Default)

```
1. Client sends JWT in Authorization header
2. Gateway validates JWT against fm-auth-service /auth/validate
3. Extract user context (user_id, email, roles)
4. Add X-User-* headers to proxied request
5. Backend services trust these headers
```

### Header Security

**Incoming Request Headers (from client):**
- ❌ `X-User-ID`: STRIPPED (security risk)
- ❌ `X-User-Email`: STRIPPED (security risk)
- ❌ `X-User-Roles`: STRIPPED (security risk)
- ✅ `Authorization`: VALIDATED and used for auth

**Proxied Request Headers (to backend):**
- ✅ `X-User-ID`: SET by gateway after JWT validation
- ✅ `X-User-Email`: SET by gateway after JWT validation
- ✅ `X-User-Roles`: SET by gateway after JWT validation
- ✅ `Authorization`: FORWARDED (backend can re-validate if needed)

**Security Guarantee**: Backend services can trust X-User-* headers because:
1. Gateway strips any untrusted X-User-* headers from client requests
2. Gateway only sets X-User-* headers after successful JWT validation
3. Backend services should only be accessible via Gateway (not directly exposed)

## Circuit Breakers

The Gateway implements circuit breakers to protect against cascading failures:

**States:**
- **CLOSED** (normal): Requests flow through normally
- **OPEN** (failing): Requests rejected immediately (503), service gets time to recover
- **HALF_OPEN** (testing): Limited requests allowed to test if service recovered

**Configuration:**
- Failure threshold: 5 consecutive failures opens circuit
- Timeout: Circuit stays open for 60 seconds
- Recovery: Successful request in HALF_OPEN closes circuit

**Example:**

```
fm-case-service is down
  ↓
5 requests fail → Circuit OPENS
  ↓
Future requests immediately return 503
  ↓
After 60s → Circuit HALF_OPEN
  ↓
1 test request succeeds → Circuit CLOSED
```

## Health Checks

The Gateway provides Kubernetes-ready health endpoints:

| Endpoint | Purpose | K8s Probe |
|----------|---------|-----------|
| `/health` | Basic health (process alive) | - |
| `/health/live` | Liveness probe | `livenessProbe` |
| `/health/ready` | Readiness probe (checks Redis, circuit breakers) | `readinessProbe` |

**Kubernetes Configuration:**

```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Client (Browser/App)                           │
│  - Sends JWT in Authorization header            │
└────────────────────┬────────────────────────────┘
                     │ HTTPS
                     ↓
┌─────────────────────────────────────────────────┐
│  fm-api-gateway (Port 8000)                     │
│  ┌───────────────────────────────────────────┐  │
│  │ 1. AuthMiddleware                         │  │
│  │    - Validate JWT                         │  │
│  │    - Extract user context                 │  │
│  │    - Strip untrusted headers              │  │
│  └───────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────┐  │
│  │ 2. RateLimitMiddleware                    │  │
│  │    - Check Redis for rate limit           │  │
│  └───────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────┐  │
│  │ 3. Routing                                │  │
│  │    - Match path pattern                   │  │
│  │    - Check circuit breaker                │  │
│  │    - Add X-User-* headers                 │  │
│  │    - Proxy to backend                     │  │
│  └───────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────┘
                     │ HTTP (internal)
                     ↓
┌─────────────────────────────────────────────────┐
│  Backend Microservices (Ports 8000-8006)        │
│  - fm-auth-service (8000)                       │
│  - fm-session-service (8001)                    │
│  - fm-knowledge-service (8002)                  │
│  - fm-case-service (8003)                       │
│  - fm-evidence-service (8004)                   │
│  - fm-investigation-service (8005)              │
│  - fm-agent-service (8006)                      │
│                                                 │
│  Trust X-User-* headers from Gateway            │
└─────────────────────────────────────────────────┘
```

## Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage report
pytest --cov=gateway --cov-report=html --cov-report=term

# Run specific test file
pytest tests/test_auth_middleware.py -v

# Run with debug output
pytest -vv -s
```

## Development Workflow

```bash
# Format code with black
black src/ tests/

# Lint with ruff
ruff check src/ tests/

# Type check with mypy (if configured)
mypy src/

# Run all quality checks
black src/ tests/ && ruff check src/ tests/ && pytest
```

## Related Projects

- [faultmaven](https://github.com/FaultMaven/faultmaven) - Main repository and documentation
- [faultmaven-copilot](https://github.com/FaultMaven/faultmaven-copilot) - Browser extension UI
- [faultmaven-deploy](https://github.com/FaultMaven/faultmaven-deploy) - Docker Compose deployment
- [fm-auth-service](https://github.com/FaultMaven/fm-auth-service) - Authentication service
- [fm-session-service](https://github.com/FaultMaven/fm-session-service) - Investigation sessions
- [fm-case-service](https://github.com/FaultMaven/fm-case-service) - Case management
- [fm-knowledge-service](https://github.com/FaultMaven/fm-knowledge-service) - Knowledge base
- [fm-evidence-service](https://github.com/FaultMaven/fm-evidence-service) - Evidence artifacts

## CI/CD

This repository uses **GitHub Actions** for automated documentation generation:

**Trigger**: Every push to `main` or `develop` branches

**Process**:
1. Generate OpenAPI spec (JSON + YAML) from all microservices
2. Validate documentation completeness (fails if endpoints lack descriptions)
3. Auto-generate this README from code
4. Create PR with changes (if on main)

See [.github/workflows/generate-docs.yml](.github/workflows/generate-docs.yml) for implementation details.

**Documentation Guarantee**: This README is always in sync with the actual code. Any endpoint changes automatically trigger documentation updates.

## License

Apache 2.0 - See [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and quality checks (`pytest && black . && ruff check .`)
5. Commit with clear messages (`git commit -m 'feat: Add amazing feature'`)
6. Push to your fork (`git push origin feature/amazing-feature`)
7. Open a Pull Request

**Code Style**: Black formatting, Ruff linting
**Commit Convention**: Conventional Commits (feat/fix/docs/refactor/test/chore)

---

**📊 Documentation Statistics**
- Total endpoints: {total_endpoints}
- Last generated: {timestamp}
- OpenAPI spec version: {version}
- Generator: scripts/generate_readme.py
- CI/CD: GitHub Actions

*This README is automatically updated on every commit to ensure zero documentation drift.*
"""

    # Write README
    readme_path = Path(__file__).parent.parent / "README.md"
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)

    print(f"✅ README.md generated successfully")
    print(f"   Location: {readme_path}")
    print(f"   Total endpoints documented: {total_endpoints}")
    print(f"   Timestamp: {timestamp}")


if __name__ == "__main__":
    main()
