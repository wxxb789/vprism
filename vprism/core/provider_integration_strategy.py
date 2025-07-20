"""
Provider Integration Strategy for vprism financial data platform.

This module implements the ProviderIntegrationStrategy class that manages
multi-provider coordination, intelligent provider selection, fault tolerance,
and data consistency validation. Designed following TDD principles with
comprehensive provider management capabilities.
"""

from __future__ import annotations

import asyncio
import logging
import statistics
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from vprism.core.exceptions import (
    DataValidationException,
    NoAvailableProviderException,
    ProviderException,
)
from vprism.core.models import (
    AssetType,
    DataPoint,
    DataQuery,
    DataResponse,
    MarketType,
    TimeFrame,
)
from vprism.core.provider_abstraction import (
    EnhancedDataProvider,
    EnhancedProviderRegistry,
)

logger = logging.getLogger(__name__)


class ProviderPriority(int, Enum):
    """Provider priority levels."""

    HIGHEST = 1  # vprism_native
    HIGH = 2  # yfinance, alpha_vantage
    MEDIUM = 3  # akshare
    LOW = 4  # fallback providers


@dataclass
class ConsistencyTolerance:
    """Configuration for data consistency validation tolerance."""

    price_tolerance_percent: float = 0.01  # 1% tolerance for price differences
    volume_tolerance_percent: float = 0.05  # 5% tolerance for volume differences
    timestamp_tolerance_seconds: int = 300  # 5 minutes tolerance for timestamps
    missing_data_tolerance: float = 0.1  # 10% missing data points allowed


@dataclass
class ValueDifference:
    """Represents a difference between two data values."""

    field_name: str
    provider1_value: Any
    provider2_value: Any
    difference_percent: float
    within_tolerance: bool


@dataclass
class ConsistencyReport:
    """Report of data consistency validation between providers."""

    query: DataQuery
    provider_results: Dict[str, DataResponse]
    consistency_score: float  # 0.0 to 1.0, higher is more consistent
    value_differences: List[ValueDifference] = field(default_factory=list)
    missing_data_points: Dict[str, int] = field(default_factory=dict)
    timestamp_differences: Dict[str, List[timedelta]] = field(default_factory=dict)
    validation_timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ProviderPerformanceMetrics:
    """Comprehensive performance metrics for a provider."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: int = 0
    min_latency_ms: int = float("inf")
    max_latency_ms: int = 0
    circuit_breaker_trips: int = 0
    last_success_time: Optional[datetime] = None
    last_failure_time: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests

    @property
    def average_latency_ms(self) -> float:
        """Calculate average latency."""
        if self.successful_requests == 0:
            return 0.0
        return self.total_latency_ms / self.successful_requests


class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit is open, requests blocked
    HALF_OPEN = "half_open"  # Testing if service is back


@dataclass
class CircuitBreaker:
    """Circuit breaker for provider fault tolerance."""

    failure_threshold: int = 5
    recovery_timeout_seconds: int = 60
    half_open_max_calls: int = 3

    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    half_open_calls: int = 0

    def should_allow_request(self) -> bool:
        """Check if request should be allowed through circuit breaker."""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            # Check if recovery timeout has passed
            if (
                self.last_failure_time
                and datetime.now() - self.last_failure_time
                > timedelta(seconds=self.recovery_timeout_seconds)
            ):
                self.state = CircuitBreakerState.HALF_OPEN
                self.half_open_calls = 0
                return True
            return False
        elif self.state == CircuitBreakerState.HALF_OPEN:
            return self.half_open_calls < self.half_open_max_calls
        return False

    def record_success(self) -> None:
        """Record successful request."""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.half_open_calls += 1
            if self.half_open_calls >= self.half_open_max_calls:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
        elif self.state == CircuitBreakerState.CLOSED:
            self.failure_count = 0

    def record_failure(self) -> None:
        """Record failed request."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
        elif (
            self.state == CircuitBreakerState.CLOSED
            and self.failure_count >= self.failure_threshold
        ):
            self.state = CircuitBreakerState.OPEN


class ProviderIntegrationStrategy:
    """
    Advanced provider integration strategy with intelligent selection,
    fault tolerance, and data consistency validation.

    Manages multiple data providers with:
    - Priority-based provider selection
    - Performance-based dynamic ranking
    - Circuit breaker fault tolerance
    - Data consistency validation
    - Load balancing and health monitoring
    """

    def __init__(self, registry: EnhancedProviderRegistry):
        """
        Initialize provider integration strategy.

        Args:
            registry: Enhanced provider registry containing available providers
        """
        self.registry = registry
        self._lock = threading.RLock()

        # Provider priorities (lower number = higher priority)
        self._provider_priorities = {
            "vprism_native": ProviderPriority.HIGHEST,
            "yfinance": ProviderPriority.HIGH,
            "alpha_vantage": ProviderPriority.HIGH,
            "akshare": ProviderPriority.MEDIUM,
        }

        # Performance tracking
        self._performance_metrics: Dict[str, ProviderPerformanceMetrics] = defaultdict(
            ProviderPerformanceMetrics
        )
        self._circuit_breakers: Dict[str, CircuitBreaker] = defaultdict(CircuitBreaker)

        # Configuration
        self._consistency_tolerance = ConsistencyTolerance()
        self._max_fallback_attempts = 3
        self._performance_weight = 0.3  # Weight of performance in selection algorithm
        self._priority_weight = 0.7  # Weight of priority in selection algorithm

    def get_provider_priorities(self) -> Dict[str, int]:
        """Get configured provider priorities."""
        return {
            name: priority.value for name, priority in self._provider_priorities.items()
        }

    def select_provider(self, query: DataQuery) -> EnhancedDataProvider:
        """
        Select the best provider for a given query using intelligent selection algorithm.

        Args:
            query: Data query to route

        Returns:
            Selected data provider

        Raises:
            NoAvailableProviderException: If no suitable provider is available
        """
        with self._lock:
            # Find providers capable of handling the query
            capable_providers = self.registry.find_capable_providers(query)

            if not capable_providers:
                raise NoAvailableProviderException(
                    "No capable provider found for query",
                    query=str(query),
                    details={"asset": query.asset.value if query.asset else None},
                )

            # Filter out circuit-broken providers
            available_providers = [
                provider
                for provider in capable_providers
                if self._circuit_breakers[provider.name].should_allow_request()
            ]

            if not available_providers:
                raise NoAvailableProviderException(
                    "All capable providers are circuit-broken",
                    query=str(query),
                    details={
                        "circuit_broken_providers": [p.name for p in capable_providers]
                    },
                )

            # Calculate composite scores for provider selection
            provider_scores = self._calculate_provider_scores(
                available_providers, query
            )

            # Select provider with highest score
            best_provider = max(provider_scores, key=provider_scores.get)

            logger.debug(
                f"Selected provider {best_provider.name} with score {provider_scores[best_provider]:.3f} "
                f"for query: {query}"
            )

            return best_provider

    def _calculate_provider_scores(
        self, providers: List[EnhancedDataProvider], query: DataQuery
    ) -> Dict[EnhancedDataProvider, float]:
        """
        Calculate composite scores for provider selection.

        Combines priority, performance metrics, and capability matching.
        """
        scores = {}

        for provider in providers:
            # Base priority score (higher priority = higher score)
            priority = self._provider_priorities.get(
                provider.name, ProviderPriority.LOW
            )
            priority_score = (5 - priority.value) / 4.0  # Normalize to 0-1

            # Performance score based on success rate and latency
            metrics = self._performance_metrics[provider.name]
            if metrics.total_requests > 0:
                performance_score = metrics.success_rate * (
                    1.0 - min(metrics.average_latency_ms / 5000.0, 0.5)
                )
            else:
                performance_score = 0.5  # Neutral score for new providers

            # Capability matching score
            capability_score = self._calculate_capability_score(provider, query)

            # Composite score
            composite_score = (
                self._priority_weight * priority_score
                + self._performance_weight * performance_score
                + 0.1 * capability_score  # Small bonus for better capability match
            )

            scores[provider] = composite_score

        return scores

    def _calculate_capability_score(
        self, provider: EnhancedDataProvider, query: DataQuery
    ) -> float:
        """Calculate capability matching score for a provider."""
        score = 0.0

        # Bonus for real-time support if query doesn't specify historical range
        if provider.capability.supports_real_time and not (query.start or query.end):
            score += 0.2

        # Bonus for low data delay
        if provider.capability.data_delay_seconds == 0:
            score += 0.3
        elif provider.capability.data_delay_seconds < 300:  # Less than 5 minutes
            score += 0.1

        # Bonus for high symbol capacity
        if query.symbols:
            symbol_ratio = (
                len(query.symbols) / provider.capability.max_symbols_per_request
            )
            if symbol_ratio <= 0.5:  # Can handle query easily
                score += 0.2
            elif symbol_ratio <= 0.8:
                score += 0.1

        return min(score, 1.0)  # Cap at 1.0

    def calculate_provider_capability_scores(
        self, query: DataQuery
    ) -> Dict[str, float]:
        """Calculate capability scores for all providers for a given query."""
        scores = {}
        all_providers = self.registry.get_all_providers()

        for provider_name, provider in all_providers.items():
            if provider.can_handle_query(query):
                scores[provider_name] = self._calculate_capability_score(
                    provider, query
                )

        return scores

    async def execute_query_with_fallback(self, query: DataQuery) -> DataResponse:
        """
        Execute query with automatic fallback to backup providers.

        Args:
            query: Data query to execute

        Returns:
            Data response from selected provider

        Raises:
            NoAvailableProviderException: If all suitable providers fail
        """
        attempted_providers = []
        last_exception = None

        for attempt in range(self._max_fallback_attempts):
            try:
                # Select best available provider
                provider = self.select_provider(query)

                # Skip if we've already tried this provider
                if provider.name in attempted_providers:
                    # Remove from available providers and try again
                    self._circuit_breakers[provider.name].record_failure()
                    continue

                attempted_providers.append(provider.name)

                # Execute query with timing
                start_time = time.time()
                response = await provider.get_data(query)
                end_time = time.time()

                latency_ms = int((end_time - start_time) * 1000)

                # Record successful request
                self.update_provider_performance(
                    provider.name, success=True, latency_ms=latency_ms
                )
                self._circuit_breakers[provider.name].record_success()

                logger.debug(
                    f"Query executed successfully by {provider.name} "
                    f"in {latency_ms}ms (attempt {attempt + 1})"
                )

                return response

            except (ProviderException, Exception) as e:
                last_exception = e

                # Get provider name from current attempt
                if attempted_providers:
                    provider_name = attempted_providers[-1]

                    # Record failed request
                    self.update_provider_performance(
                        provider_name, success=False, latency_ms=5000
                    )
                    self._circuit_breakers[provider_name].record_failure()

                    # Mark provider as unhealthy
                    self.registry.update_provider_health(provider_name, False)

                    logger.warning(
                        f"Provider {provider_name} failed (attempt {attempt + 1}): {e}"
                    )

                # Continue to next attempt
                continue

        # All attempts failed
        raise NoAvailableProviderException(
            "All capable providers failed to execute query",
            query=str(query),
            attempted_providers=attempted_providers,
            details={"last_error": str(last_exception) if last_exception else None},
        )

    def update_provider_performance(
        self, provider_name: str, success: bool, latency_ms: int
    ) -> None:
        """
        Update provider performance metrics.

        Args:
            provider_name: Name of the provider
            success: Whether the request was successful
            latency_ms: Request latency in milliseconds
        """
        with self._lock:
            metrics = self._performance_metrics[provider_name]

            metrics.total_requests += 1

            if success:
                metrics.successful_requests += 1
                metrics.total_latency_ms += latency_ms
                metrics.min_latency_ms = min(metrics.min_latency_ms, latency_ms)
                metrics.max_latency_ms = max(metrics.max_latency_ms, latency_ms)
                metrics.last_success_time = datetime.now()
            else:
                metrics.failed_requests += 1
                metrics.last_failure_time = datetime.now()

            logger.debug(
                f"Updated performance for {provider_name}: "
                f"success_rate={metrics.success_rate:.3f}, "
                f"avg_latency={metrics.average_latency_ms:.1f}ms"
            )

    def mark_provider_unhealthy(self, provider_name: str) -> None:
        """Mark a provider as unhealthy."""
        self.registry.update_provider_health(provider_name, False)
        logger.info(f"Marked provider {provider_name} as unhealthy")

    def mark_provider_healthy(self, provider_name: str) -> None:
        """Mark a provider as healthy."""
        self.registry.update_provider_health(provider_name, True)
        logger.info(f"Marked provider {provider_name} as healthy")

    def is_provider_circuit_broken(self, provider_name: str) -> bool:
        """Check if a provider's circuit breaker is open."""
        return self._circuit_breakers[provider_name].state == CircuitBreakerState.OPEN

    def get_provider_performance_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get comprehensive performance statistics for all providers."""
        with self._lock:
            stats = {}

            for provider_name, metrics in self._performance_metrics.items():
                circuit_breaker = self._circuit_breakers[provider_name]

                stats[provider_name] = {
                    "total_requests": metrics.total_requests,
                    "successful_requests": metrics.successful_requests,
                    "failed_requests": metrics.failed_requests,
                    "success_rate": metrics.success_rate,
                    "average_latency_ms": metrics.average_latency_ms,
                    "min_latency_ms": metrics.min_latency_ms
                    if metrics.min_latency_ms != float("inf")
                    else 0,
                    "max_latency_ms": metrics.max_latency_ms,
                    "circuit_breaker_state": circuit_breaker.state.value,
                    "circuit_breaker_trips": metrics.circuit_breaker_trips,
                    "last_success_time": metrics.last_success_time.isoformat()
                    if metrics.last_success_time
                    else None,
                    "last_failure_time": metrics.last_failure_time.isoformat()
                    if metrics.last_failure_time
                    else None,
                }

            return stats

    async def validate_data_consistency(
        self, query: DataQuery, providers: List[str], tolerance: Optional[float] = None
    ) -> ConsistencyReport:
        """
        Validate data consistency between multiple providers.

        Args:
            query: Data query to validate
            providers: List of provider names to compare
            tolerance: Custom tolerance for consistency validation

        Returns:
            Consistency report with detailed comparison results
        """
        if tolerance is not None:
            # Create custom tolerance configuration
            custom_tolerance = ConsistencyTolerance(
                price_tolerance_percent=tolerance,
                volume_tolerance_percent=tolerance
                * 5,  # Volume typically has higher variance
            )
        else:
            custom_tolerance = self._consistency_tolerance

        # Get data from all specified providers
        provider_results = {}

        for provider_name in providers:
            provider = self.registry.get_all_providers().get(provider_name)
            if provider and provider.can_handle_query(query):
                try:
                    response = await provider.get_data(query)
                    provider_results[provider_name] = response
                except Exception as e:
                    logger.warning(
                        f"Failed to get data from {provider_name} for consistency check: {e}"
                    )

        if len(provider_results) < 2:
            raise DataValidationException(
                "Need at least 2 providers for consistency validation",
                details={"available_providers": list(provider_results.keys())},
            )

        # Perform consistency analysis
        consistency_score, value_differences = self._analyze_data_consistency(
            provider_results, custom_tolerance
        )

        return ConsistencyReport(
            query=query,
            provider_results=provider_results,
            consistency_score=consistency_score,
            value_differences=value_differences,
        )

    def _analyze_data_consistency(
        self, provider_results: Dict[str, DataResponse], tolerance: ConsistencyTolerance
    ) -> Tuple[float, List[ValueDifference]]:
        """
        Analyze data consistency between provider results.

        Returns:
            Tuple of (consistency_score, value_differences)
        """
        if len(provider_results) < 2:
            return 1.0, []

        provider_names = list(provider_results.keys())
        value_differences = []
        total_comparisons = 0
        consistent_comparisons = 0

        # Compare each pair of providers
        for i in range(len(provider_names)):
            for j in range(i + 1, len(provider_names)):
                provider1_name = provider_names[i]
                provider2_name = provider_names[j]

                data1 = provider_results[provider1_name].data
                data2 = provider_results[provider2_name].data

                # Compare data points
                pair_differences = self._compare_data_points(
                    data1, data2, provider1_name, provider2_name, tolerance
                )

                value_differences.extend(pair_differences)

                # Count consistent vs inconsistent comparisons
                for diff in pair_differences:
                    total_comparisons += 1
                    if diff.within_tolerance:
                        consistent_comparisons += 1

        # Calculate overall consistency score
        if total_comparisons == 0:
            consistency_score = 1.0
        else:
            consistency_score = consistent_comparisons / total_comparisons

        return consistency_score, value_differences

    def _compare_data_points(
        self,
        data1: List[DataPoint],
        data2: List[DataPoint],
        provider1_name: str,
        provider2_name: str,
        tolerance: ConsistencyTolerance,
    ) -> List[ValueDifference]:
        """Compare data points between two providers."""
        differences = []

        # Create symbol-timestamp maps for efficient lookup
        data1_map = {(dp.symbol, dp.timestamp): dp for dp in data1}
        data2_map = {(dp.symbol, dp.timestamp): dp for dp in data2}

        # Find common data points
        common_keys = set(data1_map.keys()) & set(data2_map.keys())

        for key in common_keys:
            dp1 = data1_map[key]
            dp2 = data2_map[key]

            # Compare price fields
            price_fields = ["open", "high", "low", "close"]
            for field in price_fields:
                val1 = getattr(dp1, field, None)
                val2 = getattr(dp2, field, None)

                if val1 is not None and val2 is not None:
                    diff_percent = abs(float(val1) - float(val2)) / float(val1) * 100
                    within_tolerance = diff_percent <= tolerance.price_tolerance_percent

                    differences.append(
                        ValueDifference(
                            field_name=f"{key[0]}_{field}",
                            provider1_value=val1,
                            provider2_value=val2,
                            difference_percent=diff_percent,
                            within_tolerance=within_tolerance,
                        )
                    )

            # Compare volume
            if dp1.volume is not None and dp2.volume is not None:
                vol_diff_percent = (
                    abs(float(dp1.volume) - float(dp2.volume)) / float(dp1.volume) * 100
                )
                within_tolerance = (
                    vol_diff_percent <= tolerance.volume_tolerance_percent
                )

                differences.append(
                    ValueDifference(
                        field_name=f"{key[0]}_volume",
                        provider1_value=dp1.volume,
                        provider2_value=dp2.volume,
                        difference_percent=vol_diff_percent,
                        within_tolerance=within_tolerance,
                    )
                )

        return differences

    def validate_provider_configurations(self) -> List[Dict[str, Any]]:
        """
        Validate provider configurations and return any issues found.

        Returns:
            List of configuration issues
        """
        issues = []
        all_providers = self.registry.get_all_providers()

        for provider_name, provider in all_providers.items():
            # Check authentication configuration
            if not provider.auth_config.is_valid():
                issues.append(
                    {
                        "provider": provider_name,
                        "type": "authentication",
                        "message": f"Invalid authentication configuration for {provider_name}",
                    }
                )

            # Check rate limiting configuration
            if provider.rate_limit.requests_per_minute <= 0:
                issues.append(
                    {
                        "provider": provider_name,
                        "type": "rate_limit",
                        "message": f"Invalid rate limit configuration for {provider_name}",
                    }
                )

            # Check capability configuration
            if not provider.capability.supported_assets:
                issues.append(
                    {
                        "provider": provider_name,
                        "type": "capability",
                        "message": f"No supported assets configured for {provider_name}",
                    }
                )

        return issues
