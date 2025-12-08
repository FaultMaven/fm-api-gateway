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
