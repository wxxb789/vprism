"""
Intelligent data router for selecting optimal data providers.

This module implements the data routing logic that selects the best data provider
for a given query based on various factors like availability, performance,
cost, and data quality.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from vprism.core.exceptions import NoAvailableProviderException
from vprism.core.interfaces import DataProvider, DataRouter
from vprism.core.models import DataQuery
from vprism.core.provider_registry import ProviderRegistry

logger = logging.getLogger(__name__)


class IntelligentDataRouter(DataRouter):
    """
    Intelligent data router that selects optimal providers.

    Uses multiple criteria to select the best provider for a query:
    - Provider availability and health
    - Query compatibility
    - Performance metrics
    - Load balancing
    - Failover capabilities
    """

    def __init__(self, registry: ProviderRegistry | None = None) -> None:
        """
        Initialize the data router.

        Args:
            registry: Provider registry to use (creates new one if None)
        """
        self._registry = registry or ProviderRegistry()
        self._provider_metrics: dict[str, dict[str, Any]] = {}
        self._last_health_check: dict[str, float] = {}
        self._health_check_interval = 300  # 5 minutes
        self._circuit_breaker_threshold = 5
        self._circuit_breaker_failures: dict[str, int] = {}
        self._circuit_breaker_last_failure: dict[str, float] = {}
        self._circuit_breaker_timeout = 60  # 1 minute

    async def route_query(self, query: DataQuery) -> DataProvider:
        """
        Select the best provider for the given query.

        Args:
            query: The data query to route

        Returns:
            DataProvider: The selected provider

        Raises:
            NoAvailableProviderException: When no suitable provider is found
        """
        # Get all compatible providers
        compatible_providers = self._registry.find_providers(query)
        
        if not compatible_providers:
            raise NoAvailableProviderException(
                "No compatible providers found for query",
                query=str(query),
                details={"asset": query.asset.value, "market": query.market.value if query.market else None}
            )

        # Filter out providers in circuit breaker state
        available_providers = []
        for provider in compatible_providers:
            if not self._is_circuit_breaker_open(provider.name):
                available_providers.append(provider)

        if not available_providers:
            # All providers are in circuit breaker state, try the one with oldest failure
            oldest_failure_provider = min(
                compatible_providers,
                key=lambda p: self._circuit_breaker_last_failure.get(p.name, 0)
            )
            logger.warning(f"All providers in circuit breaker state, trying {oldest_failure_provider.name}")
            return oldest_failure_provider

        # Perform health checks if needed
        await self._check_provider_health_if_needed(available_providers)

        # Get healthy providers
        healthy_providers = [
            provider for provider in available_providers
            if self._registry._provider_health.get(provider.name, False)
        ]

        if not healthy_providers:
            raise NoAvailableProviderException(
                "No healthy providers available for query",
                query=str(query),
                attempted_providers=[p.name for p in available_providers]
            )

        # Select the best provider using scoring algorithm
        selected_provider = self._select_best_provider(healthy_providers, query)
        
        logger.info(f"Selected provider {selected_provider.name} for query: {query.asset}")
        return selected_provider

    def register_provider(self, provider: DataProvider) -> None:
        """
        Register a new data provider.

        Args:
            provider: The provider to register
        """
        self._registry.register_provider(provider)
        self._initialize_provider_metrics(provider.name)

    def unregister_provider(self, provider_name: str) -> bool:
        """
        Unregister a data provider.

        Args:
            provider_name: Name of provider to unregister

        Returns:
            bool: True if provider was unregistered
        """
        result = self._registry.unregister_provider(provider_name)
        if result:
            self._cleanup_provider_metrics(provider_name)
        return result

    def get_available_providers(self, query: DataQuery) -> list[DataProvider]:
        """
        Get all providers that can handle the query.

        Args:
            query: The data query

        Returns:
            List of compatible providers
        """
        return self._registry.find_providers(query)

    def record_provider_success(self, provider_name: str, response_time: float) -> None:
        """
        Record a successful provider response.

        Args:
            provider_name: Name of the provider
            response_time: Response time in seconds
        """
        if provider_name not in self._provider_metrics:
            self._initialize_provider_metrics(provider_name)

        metrics = self._provider_metrics[provider_name]
        metrics["total_requests"] += 1
        metrics["successful_requests"] += 1
        metrics["total_response_time"] += response_time
        metrics["last_success_time"] = time.time()

        # Reset circuit breaker on success
        self._circuit_breaker_failures[provider_name] = 0

        # Update average response time
        metrics["average_response_time"] = (
            metrics["total_response_time"] / metrics["successful_requests"]
        )

        logger.debug(f"Recorded success for {provider_name}: {response_time:.3f}s")

    def record_provider_failure(self, provider_name: str, error: Exception) -> None:
        """
        Record a provider failure.

        Args:
            provider_name: Name of the provider
            error: The error that occurred
        """
        if provider_name not in self._provider_metrics:
            self._initialize_provider_metrics(provider_name)

        metrics = self._provider_metrics[provider_name]
        metrics["total_requests"] += 1
        metrics["failed_requests"] += 1
        metrics["last_failure_time"] = time.time()

        # Update circuit breaker
        self._circuit_breaker_failures[provider_name] = (
            self._circuit_breaker_failures.get(provider_name, 0) + 1
        )
        self._circuit_breaker_last_failure[provider_name] = time.time()

        # Update failure rate
        if metrics["total_requests"] > 0:
            metrics["failure_rate"] = metrics["failed_requests"] / metrics["total_requests"]

        logger.warning(f"Recorded failure for {provider_name}: {error}")

    def get_provider_metrics(self, provider_name: str) -> dict[str, Any]:
        """
        Get metrics for a specific provider.

        Args:
            provider_name: Name of the provider

        Returns:
            Dictionary containing provider metrics
        """
        return self._provider_metrics.get(provider_name, {}).copy()

    def get_all_provider_metrics(self) -> dict[str, dict[str, Any]]:
        """
        Get metrics for all providers.

        Returns:
            Dictionary mapping provider names to their metrics
        """
        return {name: metrics.copy() for name, metrics in self._provider_metrics.items()}

    def reset_provider_metrics(self, provider_name: str) -> None:
        """
        Reset metrics for a specific provider.

        Args:
            provider_name: Name of the provider
        """
        if provider_name in self._provider_metrics:
            self._initialize_provider_metrics(provider_name)

    async def health_check_all_providers(self) -> dict[str, bool]:
        """
        Perform health check on all registered providers.

        Returns:
            Dictionary mapping provider names to health status
        """
        return await self._registry.check_all_provider_health()

    def _select_best_provider(
        self, providers: list[DataProvider], query: DataQuery
    ) -> DataProvider:
        """
        Select the best provider from a list of candidates.

        Uses a scoring algorithm that considers:
        - Response time
        - Failure rate
        - Last success time
        - Load balancing

        Args:
            providers: List of candidate providers
            query: The query context

        Returns:
            The best provider
        """
        if len(providers) == 1:
            return providers[0]

        scored_providers = []
        for provider in providers:
            score = self._calculate_provider_score(provider.name, query)
            scored_providers.append((provider, score))

        # Sort by score (higher is better)
        scored_providers.sort(key=lambda x: x[1], reverse=True)
        
        best_provider = scored_providers[0][0]
        logger.debug(f"Provider scores: {[(p.name, s) for p, s in scored_providers]}")
        
        return best_provider

    def _calculate_provider_score(self, provider_name: str, query: DataQuery) -> float:
        """
        Calculate a score for a provider based on various metrics.

        Args:
            provider_name: Name of the provider
            query: The query context

        Returns:
            Provider score (higher is better)
        """
        if provider_name not in self._provider_metrics:
            # New provider gets neutral score
            return 50.0

        metrics = self._provider_metrics[provider_name]
        score = 100.0  # Start with perfect score

        # Penalize high failure rate
        failure_rate = metrics.get("failure_rate", 0.0)
        score -= failure_rate * 50  # Up to -50 points for 100% failure rate

        # Penalize slow response times
        avg_response_time = metrics.get("average_response_time", 1.0)
        if avg_response_time > 1.0:  # Penalize if slower than 1 second
            score -= min(avg_response_time * 10, 30)  # Up to -30 points

        # Bonus for recent successful requests
        last_success = metrics.get("last_success_time", 0)
        time_since_success = time.time() - last_success
        if time_since_success < 300:  # Within 5 minutes
            score += 10

        # Load balancing: slightly prefer less used providers
        total_requests = metrics.get("total_requests", 0)
        if total_requests > 0:
            # Small penalty for heavily used providers
            score -= min(total_requests / 1000, 5)  # Up to -5 points

        # Add small random factor for load balancing between equivalent providers
        import random
        score += random.uniform(-2, 2)  # Small random adjustment

        return max(score, 0.0)  # Ensure non-negative score

    def _is_circuit_breaker_open(self, provider_name: str) -> bool:
        """
        Check if circuit breaker is open for a provider.

        Args:
            provider_name: Name of the provider

        Returns:
            True if circuit breaker is open (provider should be avoided)
        """
        failures = self._circuit_breaker_failures.get(provider_name, 0)
        if failures < self._circuit_breaker_threshold:
            return False

        last_failure = self._circuit_breaker_last_failure.get(provider_name, 0)
        time_since_failure = time.time() - last_failure

        # Circuit breaker opens after threshold failures
        # and stays open for the timeout period
        return time_since_failure < self._circuit_breaker_timeout

    async def _check_provider_health_if_needed(
        self, providers: list[DataProvider]
    ) -> None:
        """
        Check provider health if enough time has passed since last check.

        Args:
            providers: List of providers to check
        """
        current_time = time.time()
        providers_to_check = []

        for provider in providers:
            last_check = self._last_health_check.get(provider.name, 0)
            if current_time - last_check > self._health_check_interval:
                providers_to_check.append(provider)

        if providers_to_check:
            # Perform health checks in parallel
            health_tasks = [
                self._check_single_provider_health(provider)
                for provider in providers_to_check
            ]
            await asyncio.gather(*health_tasks, return_exceptions=True)

    async def _check_single_provider_health(self, provider: DataProvider) -> None:
        """
        Check health of a single provider.

        Args:
            provider: The provider to check
        """
        try:
            is_healthy = await provider.health_check()
            self._registry.update_provider_health(provider.name, is_healthy)
            self._last_health_check[provider.name] = time.time()
        except Exception as e:
            logger.error(f"Health check failed for {provider.name}: {e}")
            self._registry.update_provider_health(provider.name, False)
            self._last_health_check[provider.name] = time.time()

    def _initialize_provider_metrics(self, provider_name: str) -> None:
        """
        Initialize metrics for a provider.

        Args:
            provider_name: Name of the provider
        """
        self._provider_metrics[provider_name] = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_response_time": 0.0,
            "average_response_time": 0.0,
            "failure_rate": 0.0,
            "last_success_time": 0.0,
            "last_failure_time": 0.0,
        }
        self._circuit_breaker_failures[provider_name] = 0

    def _cleanup_provider_metrics(self, provider_name: str) -> None:
        """
        Clean up metrics for a provider.

        Args:
            provider_name: Name of the provider
        """
        self._provider_metrics.pop(provider_name, None)
        self._circuit_breaker_failures.pop(provider_name, None)
        self._circuit_breaker_last_failure.pop(provider_name, None)
        self._last_health_check.pop(provider_name, None)