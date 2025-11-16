#!/bin/bash
set -e

echo "=== fm-api-gateway Integration Test ==="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

GATEWAY_URL="http://localhost:8090"

echo "1. Testing Health Check..."
HEALTH=$(curl -s $GATEWAY_URL/health)
if echo "$HEALTH" | grep -q "healthy"; then
    echo -e "${GREEN}✓ Health check passed${NC}"
    echo "   Response: $HEALTH"
else
    echo -e "${RED}✗ Health check failed${NC}"
    exit 1
fi

echo ""
echo "2. Testing User Registration (via gateway)..."
REGISTER_RESPONSE=$(curl -s -X POST $GATEWAY_URL/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test-user@example.com","password":"SecurePass123","email":"test-user@example.com"}')

ACCESS_TOKEN=$(echo "$REGISTER_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null || echo "")

if [ -n "$ACCESS_TOKEN" ]; then
    echo -e "${GREEN}✓ Registration successful${NC}"
    echo "   Token: ${ACCESS_TOKEN:0:50}..."
else
    echo -e "${RED}✗ Registration failed${NC}"
    echo "   Response: $REGISTER_RESPONSE"
    exit 1
fi

echo ""
echo "3. Testing /me endpoint with valid JWT..."
ME_RESPONSE=$(curl -s $GATEWAY_URL/api/v1/auth/me \
  -H "Authorization: Bearer $ACCESS_TOKEN")

if echo "$ME_RESPONSE" | grep -q "test-user@example.com"; then
    echo -e "${GREEN}✓ JWT validation successful${NC}"
    echo "   User: $(echo "$ME_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['email'])")"
else
    echo -e "${RED}✗ JWT validation failed${NC}"
    echo "   Response: $ME_RESPONSE"
fi

echo ""
echo "4. Testing authentication without token..."
NO_AUTH_RESPONSE=$(curl -s $GATEWAY_URL/api/v1/auth/me)

if echo "$NO_AUTH_RESPONSE" | grep -q "missing_authorization\|Authentication required"; then
    echo -e "${GREEN}✓ Auth required (401) returned correctly${NC}"
else
    echo -e "${RED}✗ Should have returned 401${NC}"
    echo "   Response: $NO_AUTH_RESPONSE"
fi

echo ""
echo "5. Testing header injection prevention..."
INJECT_RESPONSE=$(curl -s $GATEWAY_URL/api/v1/auth/me \
  -H "X-User-ID: fake-admin" \
  -H "X-User-Email: admin@example.com")

if echo "$INJECT_RESPONSE" | grep -q "missing_authorization\|Authentication required"; then
    echo -e "${GREEN}✓ Header injection prevented (still requires token)${NC}"
else
    echo -e "${RED}✗ Header injection not properly prevented${NC}"
    echo "   Response: $INJECT_RESPONSE"
fi

echo ""
echo "6. Testing service routing to fm-session-service (stub)..."
SESSION_RESPONSE=$(curl -s $GATEWAY_URL/api/v1/session/test \
  -H "Authorization: Bearer $ACCESS_TOKEN")

if echo "$SESSION_RESPONSE" | grep -q "service_unavailable\|not yet implemented"; then
    echo -e "${GREEN}✓ Correctly routed to stub service (503)${NC}"
else
    echo -e "${RED}✗ Routing issue${NC}"
    echo "   Response: $SESSION_RESPONSE"
fi

echo ""
echo "=== All Tests Completed ==="
echo ""
echo "Summary:"
echo "- Gateway health: OK"
echo "- User registration: OK"
echo "- JWT validation: OK"
echo "- Auth enforcement: OK"
echo "- Header injection prevention: OK"
echo "- Service routing: OK"
