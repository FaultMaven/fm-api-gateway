#!/usr/bin/env python3
"""Generate locked OpenAPI specification from API Gateway.

This script fetches the unified OpenAPI spec from the running API Gateway
and saves it as a version-controlled locked snapshot.

Usage:
    python3 scripts/lock_openapi.py
    python3 scripts/lock_openapi.py --gateway-url http://localhost:8090
    python3 scripts/lock_openapi.py --output docs/api/openapi.locked.yaml
    python3 scripts/lock_openapi.py --format json

Examples:
    # Default (localhost, YAML output)
    python3 scripts/lock_openapi.py

    # Production gateway
    python3 scripts/lock_openapi.py --gateway-url https://api.faultmaven.ai:8090

    # JSON output instead of YAML
    python3 scripts/lock_openapi.py --format json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

try:
    import httpx
except ImportError:
    print("Error: httpx not installed")
    print("Install it with: pip install httpx")
    sys.exit(1)

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


class Colors:
    """ANSI color codes for terminal output."""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

    @classmethod
    def disable(cls):
        """Disable colors (for non-TTY output)."""
        cls.RED = cls.GREEN = cls.YELLOW = cls.BLUE = cls.NC = ''


def print_header(text: str):
    """Print section header."""
    print("=" * 70)
    print(f"  {text}")
    print("=" * 70)
    print()


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.GREEN}✓ {text}{Colors.NC}")


def print_error(text: str):
    """Print error message."""
    print(f"{Colors.RED}✗ {text}{Colors.NC}", file=sys.stderr)


def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.NC}")


def check_gateway_health(gateway_url: str) -> bool:
    """Check if API Gateway is accessible.

    Args:
        gateway_url: Base URL of the API Gateway

    Returns:
        True if gateway is accessible, False otherwise
    """
    try:
        response = httpx.get(f"{gateway_url}/health", timeout=10.0)
        response.raise_for_status()
        return True
    except httpx.HTTPError:
        return False


def fetch_openapi_spec(gateway_url: str) -> dict:
    """Fetch OpenAPI specification from API Gateway.

    Args:
        gateway_url: Base URL of the API Gateway

    Returns:
        OpenAPI spec as dictionary

    Raises:
        httpx.HTTPError: If fetch fails
    """
    response = httpx.get(f"{gateway_url}/openapi.json", timeout=30.0)
    response.raise_for_status()
    return response.json()


def save_spec(spec: dict, output_file: Path, format: str = "yaml") -> None:
    """Save OpenAPI spec to file.

    Args:
        spec: OpenAPI specification dictionary
        output_file: Path to output file
        format: Output format ("yaml" or "json")
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)

    if format == "yaml":
        if not YAML_AVAILABLE:
            print_warning("PyYAML not installed, falling back to JSON")
            print("Install it with: pip install pyyaml")
            format = "json"
            output_file = output_file.with_suffix('.json')

    if format == "yaml":
        with open(output_file, 'w') as f:
            yaml.dump(spec, f, sort_keys=False, default_flow_style=False, allow_unicode=True)
    else:
        with open(output_file, 'w') as f:
            json.dump(spec, f, indent=2, ensure_ascii=False)

    print_success(f"Saved as {format.upper()}: {output_file}")


def print_spec_summary(spec: dict) -> None:
    """Print summary of OpenAPI specification.

    Args:
        spec: OpenAPI specification dictionary
    """
    print_header("Specification Summary")

    info = spec.get("info", {})
    paths = spec.get("paths", {})
    components = spec.get("components", {})
    metadata = info.get("x-aggregation-metadata", {})

    print(f"Title:             {info.get('title', 'N/A')}")
    print(f"Version:           {info.get('version', 'N/A')}")
    print(f"Total Endpoints:   {len(paths)}")
    print(f"Total Schemas:     {len(components.get('schemas', {}))}")
    print()

    successful = metadata.get("successful_services", [])
    failed = metadata.get("failed_services", [])

    if successful:
        print(f"Successful Services: {', '.join(successful)}")

    if failed:
        print_warning(f"Failed Services:     {', '.join(failed)}")
        print()
        print_warning("Some services failed to provide OpenAPI specs.")
        print("  This locked spec is incomplete. Fix service issues and re-run.")

    print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate locked OpenAPI specification from API Gateway",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s
  %(prog)s --gateway-url http://localhost:8090
  %(prog)s --output docs/api/openapi.locked.production.yaml
  %(prog)s --format json
        """
    )

    parser.add_argument(
        "--gateway-url",
        default="http://localhost:8090",
        help="API Gateway base URL (default: http://localhost:8090)"
    )

    parser.add_argument(
        "--output",
        default="docs/api/openapi.locked.yaml",
        type=Path,
        help="Output file path (default: docs/api/openapi.locked.yaml)"
    )

    parser.add_argument(
        "--format",
        choices=["yaml", "json"],
        default="yaml",
        help="Output format (default: yaml)"
    )

    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output"
    )

    args = parser.parse_args()

    if args.no_color or not sys.stdout.isatty():
        Colors.disable()

    # Print header
    print_header("FaultMaven OpenAPI Spec Lock Utility")
    print(f"Gateway URL:  {args.gateway_url}")
    print(f"Output File:  {args.output}")
    print(f"Format:       {args.format.upper()}")
    print()

    # Check if API Gateway is accessible
    print("Checking if API Gateway is accessible...")
    if not check_gateway_health(args.gateway_url):
        print_error(f"API Gateway is not accessible at {args.gateway_url}")
        print()
        print("Please ensure:")
        print("  1. API Gateway is running")
        print("  2. All microservices are started")
        print("  3. The URL is correct")
        print()
        print("To start services:")
        print("  docker-compose up -d")
        print()
        sys.exit(1)

    print_success("API Gateway is accessible")
    print()

    # Fetch OpenAPI spec
    print(f"Fetching unified OpenAPI spec from {args.gateway_url}/openapi.json...")
    try:
        spec = fetch_openapi_spec(args.gateway_url)
        print_success("Fetched OpenAPI spec")
        print()
    except httpx.HTTPError as e:
        print_error(f"Failed to fetch OpenAPI spec: {e}")
        sys.exit(1)

    # Save spec
    print(f"Saving spec as {args.format.upper()}...")
    try:
        save_spec(spec, args.output, args.format)
        print()
    except Exception as e:
        print_error(f"Failed to save spec: {e}")
        sys.exit(1)

    # Print summary
    print_spec_summary(spec)

    # Success message
    print_header("Success: Locked OpenAPI spec generated")
    print("Next steps:")
    print()
    print("  1. Review the changes:")
    print(f"     git diff {args.output}")
    print()
    print("  2. If this looks correct, commit the locked spec:")
    print(f"     git add {args.output}")
    print('     git commit -m "docs: update locked OpenAPI spec for v2.x.x"')
    print()
    print("  3. The locked spec is now the baseline for breaking change detection")
    print()


if __name__ == "__main__":
    main()
