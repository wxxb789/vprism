"""
Intelligent data router for vprism financial data platform.

This module implements the DataRouter class that provides intelligent routing
of data queries to the most suitable providers based on capabilities, performance,
health status, and other factors. Includes provider scoring, fault tolerance,
and performance monitoring.
"""

from __future__ import annotations

import asyncio
import logging
import random
import threading
import time
from collections import defaultdict
from datetime import datetime
from enum import Enum
from typing import Any

from vprism.core.exceptions import (
    NoAvailableProviderException,
    ProviderException,
    RateLimitException,
    CircuitBreakerOpenException,
    ServiceUnavailableException,
    TimeoutException,
)
from vprism.core.fault_tolerance import (
    FaultToleranceManager,
    CircuitBreakerConfig,
    RetryConfig,
    HealthCheckConfig,
    fault_tolerance_manager,
)
from vprism.core.models import DataQuery, DataResponse
from vprism.core.provider_abstraction import (
    EnhancedDataProvider,
    EnhancedProviderRegistry,
)

logger = logging.getLogger(__name__)


class RoutingStrategy(str, Enum):
    """Routing strategies for provider selection."""
    
    INTELLIGENT = "intelligent"  # Smart selection based on performance and capabilities
    ROUND_ROBIN = "round_robin"  # Rotate through providers in order
    RANDOM = "random"           # Random selection from capable providers
    WEIGHTED = "weighted"       # Weighted selection based on provider scores


class ProviderPerformanceRecord:
    """Record of a single provider performance measurement."""

    def __init__(
        self, success: bool, latency_ms: int, timestamp: datetime | None = None
    ):
        self.success = success
        self.latency_ms = latency_ms
        self.timestamp = timestamp or datetime.now()


class DataRouter:
    """
    Intelligent data router for financial data queries.

    Routes queries to the most suitable data providers based on:
    - Provider capabilities and query requirements
    - Provider performance scores and historical performance
    - Provider health status
    - Data quality and latency requirements

    Includes fault tolerance with automatic fallback and circuit breaker behavior.
    """

    def __init__(
        self, 
        registry: EnhancedProviderRegistry,
        routing_strategy: RoutingStrategy = RoutingStrategy.INTELLIGENT,
        health_check_interval: int = 300,
        max_concurrent_health_checks: int = 10,
        enable_caching: bool = True,
        score_decay_factor: float = 0.95,
        fault_tolerance_manager: Optional[FaultToleranceManager] = None,
        enable_circuit_breaker: bool = True,
        enable_retry: bool = True,
        **kwargs
    ):
        """
        Initialize DataRouter with provider registry.

        Args:
            registry: Enhanced provider registry containing available providers
            routing_strategy: Strategy to use for provider selection
            health_check_interval: Interval between health checks in seconds
            max_concurrent_health_checks: Maximum concurrent health checks
            enable_caching: Whether to enable caching
            score_decay_factor: Factor for score decay over time
            fault_tolerance_manager: Fault tolerance manager instance
            enable_circuit_breaker: Whether to enable circuit breaker protection
            enable_retry: Whether to enable retry mechanism
            **kwargs: Additional configuration options
        """
        self.registry = registry
        self.routing_strategy = routing_strategy
        self.health_check_interval = health_check_interval
        self.max_concurrent_health_checks = max_concurrent_health_checks
        self.enable_caching = enable_caching
        self.score_decay_factor = score_decay_factor
        self.fault_tolerance_manager = fault_tolerance_manager or fault_tolerance_manager
        self.enable_circuit_breaker = enable_circuit_breaker
        self.enable_retry = enable_retry
        
        self._provider_scores: dict[str, float] = {}
        self._provider_performance_history: dict[
            str, list[ProviderPerformanceRecord]
        ] = defaultdict(list)
        self._provider_routing_counts: dict[str, int] = defaultdict(int)  # Track routing selections
        self._lock = threading.RLock()  # Reentrant lock for thread safety
        self._round_robin_index = 0  # For round-robin strategy
        self._background_tasks: list[asyncio.Task] = []
        self._health_check_running = False

        # Configuration
        self._max_history_per_provider = 1000
        self._min_score = 0.1
        self._max_score = 2.0
        self._failure_penalty = -0.2
        self._success_bonus = 0.1
        self._latency_penalty_factor = 0.00001  # Penalty per ms of latency
        self._max_fallback_attempts = 3
        
        # Initialize fault tolerance for each provider
        self._setup_fault_tolerance()

    def register_provider(self, provider: EnhancedDataProvider) -> None:
        """
        Register a provider with the router's registry.

        Args:
            provider: Provider to register
        """
        self.registry.register_provider(provider)
        self._setup_provider_fault_tolerance(provider)

    def _setup_fault_tolerance(self) -> None:
        """Setup fault tolerance for all registered providers."""
        for provider in self.registry.get_all_providers().values():
            self._setup_provider_fault_tolerance(provider)

    def _setup_provider_fault_tolerance(self, provider: EnhancedDataProvider) -> None:
        """Setup fault tolerance for a specific provider."""
        if not self.enable_circuit_breaker and not self.enable_retry:
            return
            
        provider_name = provider.name
        
        # Setup circuit breaker
        if self.enable_circuit_breaker:
            circuit_breaker_config = CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=60,
                success_threshold=3,
                timeout=30.0,
                expected_exception_types=(
                    ProviderException,
                    RateLimitException,
                    TimeoutException,
                    Exception,
                )
            )
            self.fault_tolerance_manager.get_or_create_circuit_breaker(
                provider_name, circuit_breaker_config
            )
        
        # Setup retry policy
        if self.enable_retry:
            retry_config = RetryConfig(
                max_attempts=3,
                base_delay=1.0,
                max_delay=30.0,
                exponential_base=2.0,
                jitter=True,
                retryable_exceptions=(
                    ProviderException,
                    RateLimitException,
                    TimeoutException,
                )
            )
            self.fault_tolerance_manager.get_or_create_retry_policy(
                provider_name, retry_config
            )
        
        # Setup health checker
        async def health_check():
            """Health check function for provider."""
            try:
                # Simple health check - try to get provider capability
                _ = provider.capability
                return True
            except Exception as e:
                logger.warning(f"Health check failed for provider {provider_name}: {e}")
                raise e
        
        health_config = HealthCheckConfig(
            interval=self.health_check_interval,
            timeout=10.0,
            failure_threshold=3,
            success_threshold=2,
        )
        
        health_checker = self.fault_tolerance_manager.register_health_checker(
            provider_name, health_check, health_config
        )
        
        # Add listener to update provider health in registry
        def on_health_status_change(name: str, status):
            from vprism.core.fault_tolerance import HealthStatus
            is_healthy = status == HealthStatus.HEALTHY
            self.registry.update_provider_health(name, is_healthy)
            logger.info(f"Provider {name} health status changed to {status.value}")
        
        health_checker.add_status_change_listener(on_health_status_change)

    async def route_query(self, query: DataQuery) -> EnhancedDataProvider:
        """
        Route a query to the most suitable provider.

        Args:
            query: Data query to route

        Returns:
            Selected data provider

        Raises:
            NoAvailableProviderException: If no suitable provider is available
        """
        with self._lock:
            # Check if a specific provider is requested
            if query.provider:
                all_providers = self.registry.get_all_providers()
                if query.provider in all_providers:
                    preferred_provider = all_providers[query.provider]
                    # Check if the preferred provider can handle the query
                    if preferred_provider.can_handle_query(query):
                        # Track routing selection
                        self._track_routing_selection(preferred_provider.name)
                        logger.debug(f"Using preferred provider: {preferred_provider.name}")
                        return preferred_provider
                    else:
                        logger.warning(f"Preferred provider {query.provider} cannot handle query, falling back")
                else:
                    logger.warning(f"Preferred provider {query.provider} not found, falling back")

            # Find providers capable of handling the query
            capable_providers = self.registry.find_capable_providers(query)

            if not capable_providers:
                raise NoAvailableProviderException(
                    "No available provider found for query",
                    query=str(query),
                    details={"asset": query.asset.value if query.asset else None},
                )

            # Select the best provider using scoring algorithm
            selected_provider = self._select_best_provider(capable_providers, query)

            # Track routing statistics (basic routing count)
            self._track_routing_selection(selected_provider.name)

            logger.debug(
                f"Routed query to provider {selected_provider.name} "
                f"(score: {self.get_provider_score(selected_provider.name):.2f})"
            )

            return selected_provider

    def _select_best_provider(
        self, providers: list[EnhancedDataProvider], query: DataQuery
    ) -> EnhancedDataProvider:
        """
        Select the best provider from a list of capable providers.

        Uses the configured routing strategy to select the provider.

        Args:
            providers: List of capable providers
            query: Original query for context

        Returns:
            Best provider based on routing strategy
        """
        if len(providers) == 1:
            return providers[0]

        if self.routing_strategy == RoutingStrategy.INTELLIGENT:
            return self._select_intelligent(providers, query)
        elif self.routing_strategy == RoutingStrategy.ROUND_ROBIN:
            return self._select_round_robin(providers)
        elif self.routing_strategy == RoutingStrategy.RANDOM:
            return self._select_random(providers)
        elif self.routing_strategy == RoutingStrategy.WEIGHTED:
            return self._select_weighted(providers, query)
        else:
            # Fallback to intelligent selection
            return self._select_intelligent(providers, query)

    def _select_intelligent(
        self, providers: list[EnhancedDataProvider], query: DataQuery
    ) -> EnhancedDataProvider:
        """
        Intelligent provider selection based on performance and capabilities.
        """
        # Calculate composite scores for each provider
        provider_scores = []

        for provider in providers:
            # Base performance score
            performance_score = self.get_provider_score(provider.name)

            # Data delay penalty (lower delay is better)
            delay_penalty = provider.capability.data_delay_seconds * 0.01

            # Capability match quality (exact matches get bonus)
            capability_bonus = self._calculate_capability_bonus(provider, query)

            # Composite score
            composite_score = performance_score - delay_penalty + capability_bonus

            provider_scores.append((provider, composite_score))

        # Sort by composite score (higher is better)
        provider_scores.sort(key=lambda x: x[1], reverse=True)

        # Use weighted random selection to add some variety while favoring better providers
        return self._weighted_random_selection(provider_scores)

    def _select_round_robin(self, providers: list[EnhancedDataProvider]) -> EnhancedDataProvider:
        """
        Round-robin provider selection.
        """
        with self._lock:
            # Sort providers by name for consistent ordering
            sorted_providers = sorted(providers, key=lambda p: p.name)
            selected_provider = sorted_providers[self._round_robin_index % len(sorted_providers)]
            self._round_robin_index += 1
            return selected_provider

    def _select_random(self, providers: list[EnhancedDataProvider]) -> EnhancedDataProvider:
        """
        Random provider selection.
        """
        return random.choice(providers)

    def _select_weighted(
        self, providers: list[EnhancedDataProvider], query: DataQuery
    ) -> EnhancedDataProvider:
        """
        Weighted provider selection based on performance scores.
        """
        # Calculate weights based on performance scores
        provider_weights = []
        for provider in providers:
            score = self.get_provider_score(provider.name)
            provider_weights.append((provider, score))

        # Use weighted random selection
        return self._weighted_random_selection(provider_weights)

    def _calculate_capability_bonus(
        self, provider: EnhancedDataProvider, query: DataQuery
    ) -> float:
        """Calculate bonus score for how well provider capabilities match query."""
        bonus = 0.0

        # Bonus for supporting real-time data if query might need it
        if provider.capability.supports_real_time and not (query.start or query.end):
            bonus += 0.05

        # Bonus for higher symbol capacity
        if query.symbols:
            symbol_ratio = (
                len(query.symbols) / provider.capability.max_symbols_per_request
            )
            if symbol_ratio <= 0.5:  # Provider can handle query easily
                bonus += 0.03

        return bonus

    def _weighted_random_selection(
        self, provider_scores: list[tuple[EnhancedDataProvider, float]]
    ) -> EnhancedDataProvider:
        """
        Select provider using weighted random selection based on scores.

        Higher scored providers have higher probability of selection,
        but lower scored providers can still be selected occasionally.
        """
        if not provider_scores:
            raise ValueError("No providers to select from")

        # Normalize scores to positive values for weighting
        min_score = min(score for _, score in provider_scores)
        if min_score < 0:
            provider_scores = [
                (provider, score - min_score + 0.1)
                for provider, score in provider_scores
            ]

        # Calculate weights
        total_weight = sum(score for _, score in provider_scores)
        if total_weight <= 0:
            # Fallback to uniform selection if all scores are zero or negative
            return random.choice([provider for provider, _ in provider_scores])

        # Weighted random selection
        rand_value = random.uniform(0, total_weight)
        cumulative_weight = 0

        for provider, score in provider_scores:
            cumulative_weight += score
            if rand_value <= cumulative_weight:
                return provider

        # Fallback (should not reach here)
        return provider_scores[0][0]

    async def execute_query(self, query: DataQuery) -> DataResponse:
        """
        Execute a query with automatic provider selection and fallback.

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
                # Route query to best available provider
                provider = await self.route_query(query)

                # Skip if we've already tried this provider
                if provider.name in attempted_providers:
                    continue

                attempted_providers.append(provider.name)

                # Execute query with fault tolerance
                response = await self._execute_with_fault_tolerance(provider, query)

                logger.debug(
                    f"Query executed successfully by {provider.name} (attempt {attempt + 1})"
                )

                return response

            except CircuitBreakerOpenException as e:
                last_exception = e
                provider_name = e.details.get("circuit_breaker")
                if provider_name:
                    logger.warning(
                        f"Circuit breaker open for provider {provider_name} (attempt {attempt + 1})"
                    )
                continue

            except (ProviderException, RateLimitException, TimeoutException) as e:
                last_exception = e

                # Get provider name from exception or current attempt
                provider_name = getattr(e, "details", {}).get("provider")
                if not provider_name and attempted_providers:
                    provider_name = attempted_providers[-1]

                if provider_name:
                    # Update provider score for failed request
                    self.update_provider_score(
                        provider_name, success=False, latency_ms=5000
                    )

                    # Mark provider as unhealthy after failure
                    self.registry.update_provider_health(provider_name, False)

                    logger.warning(
                        f"Provider {provider_name} failed (attempt {attempt + 1}): {e}"
                    )

                # Continue to next attempt
                continue

            except Exception as e:
                # Unexpected error - log and continue
                last_exception = e
                logger.error(
                    f"Unexpected error in query execution (attempt {attempt + 1}): {e}"
                )
                continue

        # All attempts failed
        raise NoAvailableProviderException(
            "All capable providers failed to execute query",
            query=str(query),
            attempted_providers=attempted_providers,
            details={"last_error": str(last_exception) if last_exception else None},
        )

    async def _execute_with_fault_tolerance(
        self, provider: EnhancedDataProvider, query: DataQuery
    ) -> DataResponse:
        """
        Execute query with fault tolerance protection.

        Args:
            provider: Data provider to use
            query: Data query to execute

        Returns:
            Data response from provider

        Raises:
            Various exceptions based on failure modes
        """
        provider_name = provider.name
        
        # Define the actual execution function
        async def execute_provider_query():
            start_time = time.time()
            response = await provider.get_data(query)
            end_time = time.time()
            
            # Calculate latency and update score
            latency_ms = int((end_time - start_time) * 1000)
            self.update_provider_score(provider_name, success=True, latency_ms=latency_ms)
            
            return response

        # Execute with fault tolerance if enabled
        if self.enable_circuit_breaker or self.enable_retry:
            circuit_breaker_config = None
            retry_config = None
            
            if self.enable_circuit_breaker:
                circuit_breaker_config = CircuitBreakerConfig(
                    failure_threshold=5,
                    recovery_timeout=60,
                    success_threshold=3,
                    timeout=30.0,
                )
            
            if self.enable_retry:
                retry_config = RetryConfig(
                    max_attempts=3,
                    base_delay=1.0,
                    max_delay=30.0,
                    exponential_base=2.0,
                    jitter=True,
                )
            
            return await self.fault_tolerance_manager.execute_with_fault_tolerance(
                provider_name,
                execute_provider_query,
                circuit_breaker_config=circuit_breaker_config,
                retry_config=retry_config,
            )
        else:
            # Execute without fault tolerance
            return await execute_provider_query()

    def update_provider_score(
        self, provider_name: str, success: bool, latency_ms: int
    ) -> None:
        """
        Update provider performance score based on request outcome.

        Args:
            provider_name: Name of the provider
            success: Whether the request was successful
            latency_ms: Request latency in milliseconds
        """
        with self._lock:
            # Get current score
            current_score = self._provider_scores.get(provider_name, 1.0)

            # Calculate score delta
            if success:
                score_delta = self._success_bonus - (
                    latency_ms * self._latency_penalty_factor
                )
            else:
                score_delta = self._failure_penalty

            # Update score with bounds
            new_score = max(
                self._min_score, min(self._max_score, current_score + score_delta)
            )
            self._provider_scores[provider_name] = new_score

            # Record performance history
            record = ProviderPerformanceRecord(success, latency_ms)
            self._provider_performance_history[provider_name].append(record)

            # Cleanup old history to prevent memory leaks
            self._cleanup_performance_history(provider_name)

            logger.debug(
                f"Updated score for {provider_name}: {current_score:.3f} -> {new_score:.3f} "
                f"(success: {success}, latency: {latency_ms}ms)"
            )

    def _cleanup_performance_history(self, provider_name: str) -> None:
        """Clean up old performance history to prevent memory leaks."""
        history = self._provider_performance_history[provider_name]
        if len(history) > self._max_history_per_provider:
            # Keep only the most recent records
            self._provider_performance_history[provider_name] = history[
                -self._max_history_per_provider :
            ]

    def get_provider_score(self, provider_name: str) -> float:
        """
        Get current performance score for a provider.

        Args:
            provider_name: Name of the provider

        Returns:
            Current performance score (1.0 is neutral)
        """
        with self._lock:
            return self._provider_scores.get(provider_name, 1.0)

    def get_provider_performance_stats(
        self, provider_name: str
    ) -> dict[str, Any] | None:
        """
        Get detailed performance statistics for a provider.

        Args:
            provider_name: Name of the provider

        Returns:
            Dictionary with performance statistics or None if no data
        """
        with self._lock:
            history = self._provider_performance_history.get(provider_name, [])
            if not history:
                return None

            # Calculate statistics
            total_requests = len(history)
            successful_requests = sum(1 for record in history if record.success)
            success_rate = (
                successful_requests / total_requests if total_requests > 0 else 0.0
            )

            latencies = [record.latency_ms for record in history]
            average_latency = sum(latencies) / len(latencies) if latencies else 0.0
            min_latency = min(latencies) if latencies else 0.0
            max_latency = max(latencies) if latencies else 0.0

            routing_count = self._provider_routing_counts.get(provider_name, 0)
            
            return {
                "total_requests": max(total_requests, routing_count),  # Use routing count if higher
                "successful_requests": successful_requests,
                "failed_requests": total_requests - successful_requests,
                "success_rate": success_rate,
                "average_latency_ms": average_latency,
                "min_latency_ms": min_latency,
                "max_latency_ms": max_latency,
                "current_score": self.get_provider_score(provider_name),
                "routing_selections": routing_count,
            }

    def get_all_provider_stats(self) -> dict[str, dict[str, Any]]:
        """
        Get performance statistics for all providers.

        Returns:
            Dictionary mapping provider names to their statistics
        """
        with self._lock:
            stats = {}

            # Include all providers from registry
            for provider_name in self.registry.get_all_providers().keys():
                provider_stats = self.get_provider_performance_stats(provider_name)
                if provider_stats is None:
                    # Provider has no history, create basic stats
                    provider_stats = {
                        "total_requests": 0,
                        "successful_requests": 0,
                        "failed_requests": 0,
                        "success_rate": 0.0,
                        "average_latency_ms": 0.0,
                        "min_latency_ms": 0.0,
                        "max_latency_ms": 0.0,
                        "current_score": self.get_provider_score(provider_name),
                    }
                stats[provider_name] = provider_stats

            return stats

    def reset_provider_score(self, provider_name: str) -> None:
        """
        Reset a provider's performance score to neutral (1.0).

        Args:
            provider_name: Name of the provider to reset
        """
        with self._lock:
            self._provider_scores[provider_name] = 1.0
            logger.info(f"Reset score for provider {provider_name} to 1.0")

    def reset_all_scores(self) -> None:
        """Reset all provider scores to neutral (1.0)."""
        with self._lock:
            for provider_name in self.registry.get_all_providers().keys():
                self._provider_scores[provider_name] = 1.0
            logger.info("Reset all provider scores to 1.0")

    def clear_performance_history(self, provider_name: str | None = None) -> None:
        """
        Clear performance history for a provider or all providers.

        Args:
            provider_name: Name of provider to clear, or None for all providers
        """
        with self._lock:
            if provider_name:
                self._provider_performance_history[provider_name].clear()
                logger.info(f"Cleared performance history for provider {provider_name}")
            else:
                self._provider_performance_history.clear()
                logger.info("Cleared performance history for all providers")

    def _track_routing_selection(self, provider_name: str) -> None:
        """Track that a provider was selected for routing."""
        with self._lock:
            self._provider_routing_counts[provider_name] += 1

    async def check_all_provider_health(self) -> dict[str, bool]:
        """
        Check health of all registered providers.

        Returns:
            Dictionary mapping provider names to health status
        """
        return await self.registry.check_all_provider_health()

    def get_provider_statistics(self) -> dict[str, Any]:
        """
        Get statistics about registered providers.

        Returns:
            Dictionary containing provider statistics
        """
        all_providers = self.registry.get_all_providers()
        healthy_providers = self.registry.get_healthy_providers()
        
        # Get detailed stats for each provider
        provider_stats = {}
        for provider_name in all_providers.keys():
            stats = self.get_provider_performance_stats(provider_name)
            if stats:
                provider_stats[provider_name] = stats
            else:
                # Provider has no history, create basic stats
                routing_count = self._provider_routing_counts.get(provider_name, 0)
                provider_stats[provider_name] = {
                    "total_requests": routing_count,
                    "successful_requests": 0,
                    "failed_requests": 0,
                    "success_rate": 0.0,
                    "average_latency_ms": 0.0,
                    "min_latency_ms": 0.0,
                    "max_latency_ms": 0.0,
                    "current_score": self.get_provider_score(provider_name),
                    "routing_selections": routing_count,
                }
        
        return {
            "total_providers": len(all_providers),
            "healthy_providers": len(healthy_providers),
            "unhealthy_providers": len(all_providers) - len(healthy_providers),
            "provider_names": list(all_providers.keys()),
            "providers": provider_stats,
        }

    async def start_background_tasks(self) -> None:
        """Start background tasks for health monitoring."""
        if self._health_check_running:
            return
            
        self._health_check_running = True
        
        # Start periodic health check task
        health_check_task = asyncio.create_task(self._periodic_health_check())
        self._background_tasks.append(health_check_task)
        
        logger.info("Started background health monitoring")

    async def stop_background_tasks(self) -> None:
        """Stop all background tasks."""
        self._health_check_running = False
        
        # Cancel all background tasks
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        self._background_tasks.clear()
        logger.info("Stopped background tasks")

    async def _periodic_health_check(self) -> None:
        """Periodic health check task."""
        while self._health_check_running:
            try:
                await self.check_all_provider_health()
                await asyncio.sleep(self.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic health check: {e}")
                await asyncio.sleep(self.health_check_interval)
