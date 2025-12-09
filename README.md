# fm-api-gateway

> **Part of [FaultMaven](https://github.com/FaultMaven/faultmaven)** —
> The AI-Powered Troubleshooting Copilot

**FaultMaven API Gateway** - Open source request routing with pluggable authentication.

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://hub.docker.com/r/faultmaven/fm-api-gateway)

## Overview

Central API gateway that routes requests to FaultMaven microservices. Supports pluggable authentication providers (fm-auth-service for PUBLIC, Supabase for PRIVATE).

**Features:**

- Request routing to all microservices
- Pluggable authentication (fm-auth JWT or Supabase)
- X-User-* header injection for downstream services
- Deployment-neutral service discovery (Docker/K8s/Local)
- Rate limiting (Redis-backed, per-IP)
- Circuit breakers (per-service, prevents cascading failures)
- CORS handling
- Unified OpenAPI documentation aggregation

## Quick Start

```bash
docker run -d -p 8090:8090 \
  -e AUTH_PROVIDER=fm-auth \
  -e FM_AUTH_URL=http://fm-auth-service:8001 \
  faultmaven/fm-api-gateway:latest
```

## Configuration

### Service Discovery (Deployment-Neutral)

The gateway uses **ServiceRegistry** from fm-core-lib for automatic service URL resolution:

| Variable | Default | Description |
|----------|---------|-------------|
| `DEPLOYMENT_MODE` | `docker` | Deployment mode: `docker`, `kubernetes`, or `local` |
| `K8S_NAMESPACE` | `faultmaven` | Kubernetes namespace (when DEPLOYMENT_MODE=kubernetes) |

**How it works:**

- **Docker mode**: Routes to `http://fm-{service}-service:{port}`
- **Kubernetes mode**: Routes to `http://fm-{service}-service.{namespace}.svc.cluster.local:{port}`
- **Local mode**: Routes to `http://localhost:{port}`

### Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `PRIMARY_AUTH_PROVIDER` | `fm-auth-service` | Auth provider: `fm-auth-service`, `supabase`, or `auth0` |
| `AUTH_REQUIRED` | `true` | Whether to enforce authentication |
| `JWK_CACHE_TTL` | `300` | JWK cache TTL in seconds |

### Gateway Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `GATEWAY_HOST` | `0.0.0.0` | Gateway bind host |
| `GATEWAY_PORT` | `8090` | Gateway bind port |
| `CORS_ORIGINS` | `http://localhost:3000,...` | Comma-separated CORS origins |
| `LOG_LEVEL` | `INFO` | Logging level |

### Legacy Service URL Overrides (Optional)

For backward compatibility, you can manually override service URLs:

| Variable | Description |
|----------|-------------|
| `FM_AUTH_SERVICE_URL` | Override auth service URL |
| `FM_SESSION_SERVICE_URL` | Override session service URL |
| `FM_CASE_SERVICE_URL` | Override case service URL |
| `FM_EVIDENCE_SERVICE_URL` | Override evidence service URL |
| `FM_INVESTIGATION_SERVICE_URL` | Override investigation service URL |
| `FM_KNOWLEDGE_SERVICE_URL` | Override knowledge service URL |
| `FM_AGENT_SERVICE_URL` | Override agent service URL |

**Note**: In most cases, rely on ServiceRegistry instead of manual overrides.

### Redis Configuration (for Rate Limiting & Circuit Breakers)

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_MODE` | `standalone` | Redis mode: `standalone` or `sentinel` |
| `REDIS_HOST` | `localhost` | Redis host (standalone mode) |
| `REDIS_PORT` | `6379` | Redis port (standalone mode) |
| `REDIS_PASSWORD` | _(empty)_ | Redis password |
| `REDIS_SENTINEL_HOSTS` | _(empty)_ | Sentinel hosts (when REDIS_MODE=sentinel) |
| `REDIS_MASTER_SET` | `mymaster` | Sentinel master name |

### Rate Limiting

Protects against DDoS and resource exhaustion:

| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_ENABLED` | `true` | Enable/disable rate limiting |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | `60` | Max requests per minute per IP |

**Behavior:**

- Redis-backed: Distributed rate limiting across gateway pods
- In-memory fallback: If Redis unavailable, uses per-process limits
- Graceful degradation: Fails open on errors (allows traffic)
- Returns `429 Too Many Requests` when limit exceeded
- Adds standard headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

### Circuit Breakers

Prevents cascading failures when backend services are unhealthy:

| Variable | Default | Description |
|----------|---------|-------------|
| `CIRCUIT_BREAKER_ENABLED` | `true` | Enable/disable circuit breaker |
| `CIRCUIT_BREAKER_FAIL_THRESHOLD` | `5` | Failures before opening circuit |
| `CIRCUIT_BREAKER_RESET_TIMEOUT` | `30` | Seconds before attempting recovery |

**States:**

- **CLOSED** (normal): All requests pass through
- **OPEN** (failing): After 5 consecutive failures, reject all requests with `503 Service Unavailable`
- **HALF_OPEN** (testing): After 30 seconds, allow one test request to check if service recovered

**What counts as a failure:**

- 5xx responses from backend
- Network timeouts
- Connection errors

**What does NOT count as a failure:**

- 4xx responses (client errors, service is healthy)
- 2xx/3xx responses (success)

## Routes

- `/api/v1/auth/*` → fm-auth-service
- `/api/v1/cases/*` → fm-case-service
- `/api/v1/sessions/*` → fm-session-service
- `/api/v1/documents/*` → fm-knowledge-service
- `/api/v1/evidence/*` → fm-evidence-service

## Unified API Documentation

The API Gateway aggregates OpenAPI specifications from all microservices and serves them as a unified spec.

### Accessing Documentation

| Method | URL | Use Case |
|--------|-----|----------|
| **Swagger UI** | `http://localhost:8090/docs` | Interactive API testing |
| **ReDoc UI** | `http://localhost:8090/redoc` | Clean documentation view |
| **Raw JSON** | `http://localhost:8090/openapi.json` | Programmatic access, code generation |

### For Frontend Developers

Generate TypeScript types from the unified spec:

```bash
# Fetch spec
curl http://localhost:8090/openapi.json > openapi.json

# Generate types
npx openapi-typescript openapi.json -o src/types/api.ts
```

Import to Postman:

```text
File → Import → Link → http://localhost:8090/openapi.json
```

### Generating Locked OpenAPI Spec

For stable API contract reference, generate a locked version:

```bash
# Start all services
docker-compose up -d

# Wait for services to be healthy
sleep 30

# Generate locked spec (bash)
./scripts/lock-openapi.sh

# OR using Python
python3 scripts/lock_openapi.py

# Review changes
git diff docs/api/openapi.locked.yaml

# Commit if stable
git add docs/api/openapi.locked.yaml
git commit -m "docs: update locked OpenAPI spec for v2.x.x"
```

**Options:**

```bash
# Custom gateway URL
./scripts/lock-openapi.sh http://production:8090

# Custom output file
./scripts/lock-openapi.sh http://localhost:8090 docs/api/openapi.locked.production.yaml

# Python with JSON output
python3 scripts/lock_openapi.py --format json --output docs/api/openapi.locked.json
```

### Admin Endpoints

**Refresh OpenAPI Cache:**

After deploying a service update, force refresh the unified spec:

```bash
curl -X POST http://localhost:8090/admin/refresh-openapi
```

Response:

```json
{
  "status": "success",
  "message": "OpenAPI spec cache cleared. Next request will fetch fresh specs from all services."
}
```

**Check OpenAPI Health:**

Verify which services are responding with OpenAPI specs:

```bash
curl http://localhost:8090/admin/openapi-health
```

Response:

```json
{
  "status": "healthy",
  "timestamp": "2.0.0",
  "aggregation": {
    "successful_services": ["auth", "session", "case", "knowledge", "evidence", "agent"],
    "failed_services": [],
    "total_paths": 47,
    "total_schemas": 89
  }
}
```

### Breaking Change Protection

The repository includes CI workflows to detect breaking API changes:

- **On Pull Request**: Compares current spec vs locked baseline
- **On Release**: Auto-generates locked spec from production

If breaking changes are detected:

1. **Bump API version**: Update from v1 → v2
2. **Update locked spec**: Run `./scripts/lock-openapi.sh`
3. **Document migration**: Add migration guide to PR

See [API_BREAKING_CHANGES.md](docs/API_BREAKING_CHANGES.md) for details.

## Contributing

See our [Contributing Guide](https://github.com/FaultMaven/.github/blob/main/CONTRIBUTING.md) for detailed guidelines.

## Support

- **Discussions:** [GitHub Discussions](https://github.com/FaultMaven/faultmaven/discussions)
- **Issues:** [GitHub Issues](https://github.com/FaultMaven/fm-api-gateway/issues)

## Related Projects

- **[faultmaven](https://github.com/FaultMaven/faultmaven)** - Main repository and documentation
- **[faultmaven-deploy](https://github.com/FaultMaven/faultmaven-deploy)** - Deployment configurations
- **[fm-auth-service](https://github.com/FaultMaven/fm-auth-service)** - Authentication service
- **[fm-case-service](https://github.com/FaultMaven/fm-case-service)** - Case management service
- **[fm-session-service](https://github.com/FaultMaven/fm-session-service)** - Session management service
- **[fm-knowledge-service](https://github.com/FaultMaven/fm-knowledge-service)** - Knowledge base service
- **[fm-evidence-service](https://github.com/FaultMaven/fm-evidence-service)** - Evidence management service

## License

Apache 2.0 - See [LICENSE](LICENSE) for details.
