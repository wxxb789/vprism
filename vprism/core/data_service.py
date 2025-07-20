"""
Unified data service for vprism financial data platform.

This module implements the DataService class that provides intelligent data retrieval
by integrating routing, caching, and provider management. It serves as the core
orchestrator for all data operations in the platform.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from vprism.core.cache import MultiLevelCache
from vprism.core.data_router import DataRouter
from vprism.core.exceptions import DataValidationException, VPrismException
from vprism.core.models import DataPoint, DataQuery, DataResponse, ResponseMetadata
from vprism.core.provider_abstraction import EnhancedProviderRegistry

logger = logging.getLogger(__name__)


class DataService:
    """
    Unified data service that orchestrates data retrieval operations.

    This service implements the core data retrieval pipeline:
    1. Query validation
    2. Cache checking
    3. Provider routing and execution
    4. Data quality validation
    5. Response metadata enhancement
    6. Cache storage

    The service integrates multiple components to provide intelligent,
    high-performance data access with fault tolerance and caching.
    """

    def __init__(
        self,
        cache: MultiLevelCache | None = None,
        router: DataRouter | None = None,
        provider_registry: EnhancedProviderRegistry | None = None,
    ):
        """
        Initialize DataService with optional component injection.

        Args:
            cache: Multi-level cache instance (creates default if None)
            router: Data router instance (creates default if None)
            provider_registry: Provider registry (creates default if None)
        """
        # Initialize components with defaults if not provided
        self.provider_registry = provider_registry or EnhancedProviderRegistry()
        self.cache = cache or MultiLevelCache()
        self.router = router or DataRouter(self.provider_registry)

        # Performance tracking
        self._request_count = 0
        self._cache_hit_count = 0

        logger.info("DataService initialized successfully")

    async def get_data(self, query: DataQuery) -> DataResponse:
        """
        Retrieve financial data using the intelligent data pipeline.

        This method implements the complete data retrieval pipeline:
        1. Validates the query
        2. Checks cache for existing data
        3. Routes to appropriate provider if cache miss
        4. Validates and enhances response
        5. Stores result in cache

        Args:
            query: Data query specification

        Returns:
            DataResponse containing requested data and metadata

        Raises:
            DataValidationException: When query validation fails
            VPrismException: When data retrieval fails
        """
        start_time = time.time()
        self._request_count += 1

        try:
            # Step 1: Validate query
            await self._validate_query(query)

            # Step 2: Check cache
            cached_response = await self.cache.get_data(query)
            if cached_response is not None:
                self._cache_hit_count += 1
                logger.debug(f"Cache hit for query: {query.cache_key()}")

                # Update metadata to reflect cache hit
                cached_response.metadata.cache_hit = True
                execution_time_ms = (time.time() - start_time) * 1000

                # Enhance metadata with current timing
                return await self._enhance_response_metadata(
                    cached_response, query, execution_time_ms, cache_hit=True
                )

            # Step 3: Execute query through router
            logger.debug(
                f"Cache miss for query: {query.cache_key()}, routing to provider"
            )
            response = await self.router.execute_query(query)

            # Step 4: Calculate execution time
            execution_time_ms = (time.time() - start_time) * 1000

            # Step 5: Enhance response metadata
            enhanced_response = await self._enhance_response_metadata(
                response, query, execution_time_ms, cache_hit=False
            )

            # Step 6: Store in cache (fire and forget)
            asyncio.create_task(self.cache.set_data(query, enhanced_response))

            logger.debug(
                f"Query executed successfully in {execution_time_ms:.2f}ms "
                f"with {len(enhanced_response.data)} records"
            )

            return enhanced_response

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Query execution failed after {execution_time_ms:.2f}ms: {e}",
                extra={"query": query.cache_key(), "error": str(e)},
            )

            # Re-raise known exceptions
            if isinstance(e, (DataValidationException, VPrismException)):
                raise

            # Wrap unexpected exceptions
            raise VPrismException(
                message=f"Unexpected error during data retrieval: {e}",
                error_code="INTERNAL_ERROR",
                details={
                    "query": query.model_dump(),
                    "execution_time_ms": execution_time_ms,
                    "original_error": str(e),
                },
            ) from e

    async def _validate_query(self, query: DataQuery) -> None:
        """
        Validate query parameters and constraints.

        Args:
            query: Query to validate

        Raises:
            DataValidationException: When validation fails
        """
        # Check for empty symbols list
        if query.symbols is not None and len(query.symbols) == 0:
            raise DataValidationException(
                message="Symbols list cannot be empty when provided",
                details={"query": query.model_dump()},
            )

        # Check for future dates
        now = datetime.now(timezone.utc)
        if query.start and query.start > now:
            raise DataValidationException(
                message="Start date cannot be in the future",
                details={
                    "start": query.start.isoformat(),
                    "current_time": now.isoformat(),
                },
            )

        if query.end and query.end > now:
            raise DataValidationException(
                message="End date cannot be in the future",
                details={
                    "end": query.end.isoformat(),
                    "current_time": now.isoformat(),
                },
            )

        # Check date range order
        if query.start and query.end and query.start > query.end:
            raise DataValidationException(
                message="Start date must be before end date",
                details={
                    "start": query.start.isoformat(),
                    "end": query.end.isoformat(),
                },
            )

    async def _calculate_data_quality_score(
        self, data_points: list[DataPoint]
    ) -> float:
        """
        Calculate data quality score based on completeness and consistency.

        Args:
            data_points: List of data points to evaluate

        Returns:
            Quality score between 0.0 and 1.0
        """
        if not data_points:
            return 0.0

        total_score = 0.0
        total_fields = 0

        for point in data_points:
            # Score based on field completeness
            field_score = 0.0
            field_count = 0

            # Core OHLCV fields
            core_fields = [point.open, point.high, point.low, point.close, point.volume]
            for field in core_fields:
                field_count += 1
                if field is not None:
                    field_score += 1.0

            # Additional fields
            if point.amount is not None:
                field_score += 0.5
                field_count += 0.5

            # Symbol and timestamp are required, so they don't affect score
            # but we verify they exist
            if not point.symbol or not point.timestamp:
                field_score *= 0.5  # Penalty for missing required fields

            total_score += field_score / field_count if field_count > 0 else 0.0
            total_fields += 1

        return total_score / total_fields if total_fields > 0 else 0.0

    async def _enhance_response_metadata(
        self,
        response: DataResponse,
        query: DataQuery,
        execution_time_ms: float,
        cache_hit: bool,
    ) -> DataResponse:
        """
        Enhance response metadata with additional information.

        Args:
            response: Original response
            query: Original query
            execution_time_ms: Execution time in milliseconds
            cache_hit: Whether this was a cache hit

        Returns:
            Response with enhanced metadata
        """
        # Calculate data quality score
        quality_score = await self._calculate_data_quality_score(response.data)

        # Create enhanced metadata
        enhanced_metadata = ResponseMetadata(
            query_time=datetime.now(timezone.utc),
            execution_time_ms=execution_time_ms,
            record_count=len(response.data),
            cache_hit=cache_hit,
            data_quality_score=quality_score,
            warnings=response.metadata.warnings
            if hasattr(response.metadata, "warnings")
            else [],
        )

        # Create new response with enhanced metadata
        return DataResponse(
            data=response.data,
            metadata=enhanced_metadata,
            source=response.source,
            query=query,  # Use original query for consistency
        )

    def get_performance_stats(self) -> dict[str, Any]:
        """
        Get performance statistics for the data service.

        Returns:
            Dictionary containing performance metrics
        """
        cache_hit_rate = (
            self._cache_hit_count / self._request_count
            if self._request_count > 0
            else 0.0
        )

        return {
            "total_requests": self._request_count,
            "cache_hits": self._cache_hit_count,
            "cache_hit_rate": cache_hit_rate,
            "provider_stats": self.router.get_all_provider_stats(),
        }

    def reset_performance_stats(self) -> None:
        """Reset performance statistics."""
        self._request_count = 0
        self._cache_hit_count = 0
        logger.info("Performance statistics reset")

    async def health_check(self) -> dict[str, Any]:
        """
        Perform health check on the data service and its components.

        Returns:
            Dictionary containing health status information
        """
        health_status = {
            "service": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": {},
        }

        try:
            # Check cache health
            cache_healthy = await self._check_cache_health()
            health_status["components"]["cache"] = (
                "healthy" if cache_healthy else "unhealthy"
            )

            # Check provider registry health
            registry_healthy = await self._check_registry_health()
            health_status["components"]["provider_registry"] = (
                "healthy" if registry_healthy else "unhealthy"
            )

            # Overall health
            all_healthy = cache_healthy and registry_healthy
            health_status["service"] = "healthy" if all_healthy else "degraded"

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            health_status["service"] = "unhealthy"
            health_status["error"] = str(e)

        return health_status

    async def _check_cache_health(self) -> bool:
        """Check if cache is healthy."""
        try:
            # Simple cache operation test
            test_key = "health_check_test"
            await self.cache.exists(test_key)
            return True
        except Exception as e:
            logger.warning(f"Cache health check failed: {e}")
            return False

    async def _check_registry_health(self) -> bool:
        """Check if provider registry is healthy."""
        try:
            # Check if registry has providers
            providers = self.provider_registry.get_all_providers()
            return len(providers) > 0
        except Exception as e:
            logger.warning(f"Provider registry health check failed: {e}")
            return False

    async def clear_cache(self) -> None:
        """Clear all cached data."""
        try:
            await self.cache.clear()
            logger.info("Cache cleared successfully")
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            raise VPrismException(
                message="Failed to clear cache",
                error_code="CACHE_ERROR",
                details={"error": str(e)},
            ) from e

    def configure(self, **kwargs: Any) -> None:
        """
        Configure the data service with new settings.

        Args:
            **kwargs: Configuration parameters
        """
        # This method can be extended to support runtime configuration
        # For now, log the configuration attempt
        logger.info(f"DataService configuration updated: {kwargs}")
