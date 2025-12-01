"""OpenAPI Specification Aggregator for Microservices

Aggregates OpenAPI specs from multiple FastAPI microservices into a unified specification.
This allows frontend developers to reference a single API documentation endpoint.

Architecture:
- Each microservice exposes /openapi.json (FastAPI default)
- API Gateway fetches and merges specs at runtime
- Unified spec served at /openapi.json and /docs

Benefits:
- Always up-to-date documentation
- Single source of truth for API contracts
- Simpler frontend integration
- Better developer experience
"""

import httpx
import logging
from typing import Dict, Any, Optional
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class OpenAPIAggregator:
    """Aggregate OpenAPI specs from multiple microservices"""

    def __init__(self, services: Dict[str, str], cache_ttl: int = 300):
        """
        Initialize OpenAPI aggregator.

        Args:
            services: Dict mapping service name to base URL
                     e.g., {"auth": "http://fm-auth-service:8000"}
            cache_ttl: Cache time-to-live in seconds (default: 5 minutes)
        """
        self.services = services
        self.cache_ttl = cache_ttl
        self._cached_spec: Optional[Dict[str, Any]] = None
        self._cache_timestamp: Optional[float] = None

    async def get_unified_spec(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Fetch and merge OpenAPI specs from all microservices.

        Args:
            force_refresh: If True, bypass cache and fetch fresh specs

        Returns:
            Unified OpenAPI specification dictionary

        Raises:
            HTTPException: If all services fail to respond
        """
        # Check cache
        if not force_refresh and self._cached_spec:
            logger.debug("Returning cached unified OpenAPI spec")
            return self._cached_spec

        logger.info("Fetching OpenAPI specs from all microservices")

        # Initialize unified spec structure
        unified_spec = {
            "openapi": "3.1.0",
            "info": {
                "title": "FaultMaven API",
                "description": (
                    "Unified API specification from all FaultMaven microservices.\n\n"
                    "This documentation aggregates endpoints from:\n"
                    "- Auth Service (authentication & user management)\n"
                    "- Session Service (session lifecycle)\n"
                    "- Case Service (troubleshooting case management)\n"
                    "- Evidence Service (file uploads & attachments)\n"
                    "- Investigation Service (hypotheses & solutions)\n"
                    "- Knowledge Service (RAG knowledge base)\n"
                    "- Agent Service (AI troubleshooting agent)\n\n"
                    "All requests should be made to the API Gateway endpoint."
                ),
                "version": "2.0.0",
                "contact": {
                    "name": "FaultMaven",
                    "url": "https://github.com/FaultMaven/faultmaven",
                },
                "license": {
                    "name": "Apache 2.0",
                    "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
                },
            },
            "servers": [
                {
                    "url": "http://localhost:8090",
                    "description": "Local development (API Gateway)",
                },
                {
                    "url": "http://127.0.0.1:8090",
                    "description": "Local development (alternative)",
                },
            ],
            "paths": {},
            "components": {
                "schemas": {},
                "securitySchemes": {},
                "responses": {},
                "parameters": {},
                "requestBodies": {},
            },
            "tags": [],
        }

        # Track which services responded
        successful_services = []
        failed_services = []

        # Fetch specs from each service
        async with httpx.AsyncClient(timeout=10.0) as client:
            for service_name, service_url in self.services.items():
                try:
                    logger.debug(f"Fetching OpenAPI spec from {service_name} at {service_url}")
                    response = await client.get(f"{service_url}/openapi.json")
                    response.raise_for_status()
                    service_spec = response.json()

                    # Merge paths
                    paths = service_spec.get("paths", {})
                    unified_spec["paths"].update(paths)
                    logger.debug(f"Merged {len(paths)} paths from {service_name}")

                    # Merge components
                    components = service_spec.get("components", {})

                    # Merge schemas
                    schemas = components.get("schemas", {})
                    unified_spec["components"]["schemas"].update(schemas)

                    # Merge security schemes
                    security = components.get("securitySchemes", {})
                    unified_spec["components"]["securitySchemes"].update(security)

                    # Merge responses
                    responses = components.get("responses", {})
                    unified_spec["components"]["responses"].update(responses)

                    # Merge parameters
                    parameters = components.get("parameters", {})
                    unified_spec["components"]["parameters"].update(parameters)

                    # Merge request bodies
                    request_bodies = components.get("requestBodies", {})
                    unified_spec["components"]["requestBodies"].update(request_bodies)

                    # Merge tags (avoid duplicates)
                    tags = service_spec.get("tags", [])
                    existing_tag_names = {tag["name"] for tag in unified_spec["tags"]}
                    for tag in tags:
                        if tag["name"] not in existing_tag_names:
                            unified_spec["tags"].append(tag)
                            existing_tag_names.add(tag["name"])

                    successful_services.append(service_name)
                    logger.info(f"✓ Successfully merged OpenAPI spec from {service_name}")

                except httpx.HTTPStatusError as e:
                    logger.warning(
                        f"✗ HTTP error fetching OpenAPI spec from {service_name}: "
                        f"{e.response.status_code}"
                    )
                    failed_services.append(service_name)

                except httpx.TimeoutException:
                    logger.warning(f"✗ Timeout fetching OpenAPI spec from {service_name}")
                    failed_services.append(service_name)

                except httpx.RequestError as e:
                    logger.warning(
                        f"✗ Request error fetching OpenAPI spec from {service_name}: {str(e)}"
                    )
                    failed_services.append(service_name)

                except Exception as e:
                    logger.error(
                        f"✗ Unexpected error fetching OpenAPI spec from {service_name}: {str(e)}"
                    )
                    failed_services.append(service_name)

        # Log summary
        logger.info(
            f"OpenAPI aggregation complete: {len(successful_services)} successful, "
            f"{len(failed_services)} failed"
        )
        if successful_services:
            logger.info(f"  ✓ Successful: {', '.join(successful_services)}")
        if failed_services:
            logger.warning(f"  ✗ Failed: {', '.join(failed_services)}")

        # If ALL services failed, raise error
        if not successful_services:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Failed to fetch OpenAPI specs from all microservices. "
                    "Services may be unavailable."
                ),
            )

        # Add metadata about aggregation
        unified_spec["info"]["x-aggregation-metadata"] = {
            "successful_services": successful_services,
            "failed_services": failed_services,
            "total_paths": len(unified_spec["paths"]),
            "total_schemas": len(unified_spec["components"]["schemas"]),
        }

        # Cache the result
        self._cached_spec = unified_spec
        logger.info(
            f"Cached unified spec: {len(unified_spec['paths'])} paths, "
            f"{len(unified_spec['components']['schemas'])} schemas"
        )

        return unified_spec

    def clear_cache(self) -> None:
        """Clear the cached OpenAPI specification"""
        self._cached_spec = None
        logger.info("OpenAPI spec cache cleared")
