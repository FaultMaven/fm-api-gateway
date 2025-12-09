#!/bin/bash
# Generate locked OpenAPI specification from API Gateway
#
# This script fetches the unified OpenAPI spec from the running API Gateway
# and saves it as a version-controlled locked snapshot.
#
# Usage:
#   ./scripts/lock-openapi.sh [GATEWAY_URL] [OUTPUT_FILE]
#
# Examples:
#   ./scripts/lock-openapi.sh
#   ./scripts/lock-openapi.sh http://localhost:8090
#   ./scripts/lock-openapi.sh http://production:8090 docs/api/openapi.locked.production.yaml

set -e  # Exit on error

# Configuration
GATEWAY_URL="${1:-${GATEWAY_URL:-http://localhost:8090}}"
OUTPUT_FILE="${2:-docs/api/openapi.locked.yaml}"
OUTPUT_DIR=$(dirname "$OUTPUT_FILE")

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "======================================================================"
echo "  FaultMaven OpenAPI Spec Lock Utility"
echo "======================================================================"
echo ""
echo "Gateway URL:  $GATEWAY_URL"
echo "Output File:  $OUTPUT_FILE"
echo ""

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Check if API Gateway is running
echo "Checking if API Gateway is accessible..."
if ! curl -sf "$GATEWAY_URL/health" > /dev/null 2>&1; then
    echo -e "${RED}✗ Error: API Gateway is not accessible at $GATEWAY_URL${NC}"
    echo ""
    echo "Please ensure:"
    echo "  1. API Gateway is running"
    echo "  2. All microservices are started"
    echo "  3. The URL is correct"
    echo ""
    echo "To start services:"
    echo "  docker-compose up -d"
    echo ""
    exit 1
fi
echo -e "${GREEN}✓ API Gateway is accessible${NC}"
echo ""

# Fetch unified OpenAPI spec
echo "Fetching unified OpenAPI spec from $GATEWAY_URL/openapi.json..."
if ! curl -sf "$GATEWAY_URL/openapi.json" -o /tmp/openapi.json; then
    echo -e "${RED}✗ Error: Failed to fetch OpenAPI spec${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Fetched OpenAPI spec${NC}"
echo ""

# Convert JSON to YAML (if yq is available)
if command -v yq &> /dev/null; then
    echo "Converting JSON to YAML..."
    yq eval -P /tmp/openapi.json > "$OUTPUT_FILE"
    echo -e "${GREEN}✓ Saved as YAML: $OUTPUT_FILE${NC}"
else
    echo -e "${YELLOW}⚠ yq not found, saving as JSON${NC}"
    cp /tmp/openapi.json "${OUTPUT_FILE%.yaml}.json"
    echo -e "${GREEN}✓ Saved as JSON: ${OUTPUT_FILE%.yaml}.json${NC}"
    echo ""
    echo "To convert to YAML, install yq:"
    echo "  brew install yq  # macOS"
    echo "  sudo apt install yq  # Ubuntu"
fi
echo ""

# Display metadata
echo "======================================================================"
echo "  Specification Summary"
echo "======================================================================"
echo ""

if command -v jq &> /dev/null; then
    # Extract metadata using jq
    TITLE=$(jq -r '.info.title' /tmp/openapi.json)
    VERSION=$(jq -r '.info.version' /tmp/openapi.json)
    TOTAL_PATHS=$(jq '.paths | length' /tmp/openapi.json)
    TOTAL_SCHEMAS=$(jq '.components.schemas | length' /tmp/openapi.json)

    # Aggregation metadata
    SUCCESSFUL_SERVICES=$(jq -r '.info."x-aggregation-metadata".successful_services | join(", ")' /tmp/openapi.json)
    FAILED_SERVICES=$(jq -r '.info."x-aggregation-metadata".failed_services | join(", ")' /tmp/openapi.json)

    echo "Title:             $TITLE"
    echo "Version:           $VERSION"
    echo "Total Endpoints:   $TOTAL_PATHS"
    echo "Total Schemas:     $TOTAL_SCHEMAS"
    echo ""
    echo "Successful Services: $SUCCESSFUL_SERVICES"

    if [ "$FAILED_SERVICES" != "null" ] && [ -n "$FAILED_SERVICES" ]; then
        echo -e "${YELLOW}Failed Services:     $FAILED_SERVICES${NC}"
        echo ""
        echo -e "${YELLOW}⚠ Warning: Some services failed to provide OpenAPI specs.${NC}"
        echo "  This locked spec is incomplete. Fix service issues and re-run."
    fi
else
    echo "Install jq to see detailed summary:"
    echo "  brew install jq  # macOS"
    echo "  sudo apt install jq  # Ubuntu"
fi
echo ""

# Cleanup
rm -f /tmp/openapi.json

echo "======================================================================"
echo -e "${GREEN}✓ Success: Locked OpenAPI spec generated${NC}"
echo "======================================================================"
echo ""
echo "Next steps:"
echo ""
echo "  1. Review the changes:"
echo "     git diff $OUTPUT_FILE"
echo ""
echo "  2. If this looks correct, commit the locked spec:"
echo "     git add $OUTPUT_FILE"
echo "     git commit -m \"docs: update locked OpenAPI spec for v2.x.x\""
echo ""
echo "  3. The locked spec is now the baseline for breaking change detection"
echo ""
