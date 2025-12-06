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
- CORS handling
- Health check aggregation

## Quick Start

```bash
docker run -d -p 8090:8090 \
  -e AUTH_PROVIDER=fm-auth \
  -e FM_AUTH_URL=http://fm-auth-service:8001 \
  faultmaven/fm-api-gateway:latest
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8090` | Gateway port |
| `AUTH_PROVIDER` | `fm-auth` | Auth provider (fm-auth or supabase) |
| `FM_AUTH_URL` | `http://localhost:8001` | fm-auth-service URL |
| `CASE_SERVICE_URL` | `http://localhost:8003` | fm-case-service URL |
| `SESSION_SERVICE_URL` | `http://localhost:8002` | fm-session-service URL |
| `KNOWLEDGE_SERVICE_URL` | `http://localhost:8004` | fm-knowledge-service URL |
| `EVIDENCE_SERVICE_URL` | `http://localhost:8005` | fm-evidence-service URL |

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
