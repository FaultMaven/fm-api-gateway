# Quick Start Guide - fm-api-gateway

## Prerequisites

- Python 3.10+
- fm-auth-service running on port 8001

## Installation

```bash
cd /home/swhouse/projects/fm-api-gateway

# Create virtual environment
python3 -m venv .venv

# Install dependencies
.venv/bin/pip install -e .
```

## Configuration

Edit `.env` if needed (defaults work with local development):

```bash
PRIMARY_AUTH_PROVIDER=fm-auth-service
FM_AUTH_SERVICE_URL=http://127.0.0.1:8001
GATEWAY_PORT=8090
```

## Running the Gateway

### Option 1: Development Mode (with hot reload)

```bash
.venv/bin/python -m gateway.main
```

Gateway will start on: http://localhost:8090

### Option 2: Production Mode (with uvicorn)

```bash
.venv/bin/uvicorn gateway.main:app --host 0.0.0.0 --port 8090
```

## Testing

Run the integration test script:

```bash
./test_gateway.sh
```

## Manual Testing

### 1. Health Check

```bash
curl http://localhost:8090/health
```

Expected: `{"status":"healthy","service":"fm-api-gateway","version":"1.0.0"}`

### 2. Register User (via gateway)

```bash
curl -X POST http://localhost:8090/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username":"test@example.com",
    "password":"SecurePass123",
    "email":"test@example.com"
  }'
```

Expected: JWT token in response

### 3. Login (via gateway)

```bash
curl -X POST http://localhost:8090/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email":"test@example.com",
    "password":"SecurePass123"
  }'
```

Save the `access_token` from the response.

### 4. Call Protected Endpoint

```bash
# Replace <TOKEN> with your access_token
curl http://localhost:8090/api/v1/auth/me \
  -H "Authorization: Bearer <TOKEN>"
```

Expected: User information (gateway validates JWT and proxies to fm-auth-service)

### 5. Test Without Token (should fail)

```bash
curl http://localhost:8090/api/v1/auth/me
```

Expected: `401 Unauthorized` with error message

## Stopping the Gateway

If running in background:

```bash
pkill -f "python -m gateway.main"
```

## Logs

Gateway logs are written to `gateway.log` when run in background mode.

View logs:

```bash
tail -f gateway.log
```

## Architecture

```
Client Request with JWT
    ↓
Gateway Middleware
    ├─ Validate JWT signature (using fm-auth-service JWK)
    ├─ Extract user context (user_id, email, roles)
    ├─ Strip client X-User-* headers (security!)
    └─ Add validated X-User-* headers
    ↓
Proxy to Backend Service
    ↓
Backend Response
```

## Next Steps

See [README.md](README.md) for complete documentation.
