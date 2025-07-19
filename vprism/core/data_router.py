"""
Intelligent data router for vprism financial data platform.

This module implements the DataRouter class that intelligently selects
the best data provider for a given query based on various factors like
availability, performance, cost, and quality. It supports multiple
routing strategies and includes health monitoring and load balancing.
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from vprism.core.exceptions import NoAvailableProviderException
from vprism.core.interfaces import DataProvider
from vprism.core.models import DataQuery
from vprism.core.provider_registry import ProviderRegistry

logger = logging.getLogger(__name__)


class RoutingStrategy(str, Enum):
    """Enumeration of routing strategies."""
    
    INTELLIGENT = "intelligent"  # Score-based intelligent routing
    ROUND_ROBIN = "round_robin"  # Round-robin load balancing
    RANDOM = "random"  # Random selection
    WEIGHTED = "weighted"  # Weighted random based on scores


@dataclass
class ProviderScore:
    """
    Tracks performance metrics for a data provider.
    
    This class maintains statistics about provider performance
    to enable intelligent routing decisions.
    """
    
    provider: DataProvider
    total_requests: int = 0
    successful_requests: int = 0
    avg_response_time: float = 0.0
    last_used: datetime | None = None
    last_error: str | None = None
    consecutive_failures: int = 0
    
    # Weighted moving averages for recent performance
    recent_success_rate: float = 1.0
    recent_response_time: float = 0.0
    
    # Additional metrics
    rate_limit_hits: int = 0
    timeout_count: int = 0
    
    @property
    def success_rate(self) -> float:
        """Calculate overall success rate."""
        if self.total_requests == 0:
            return 1.0  # Default for new providers
        return self.successful_requests / self.total_requests
    
    @success_rate.setter
    def success_rate(self, value: float) -> None:
        """Set success rate by adjusting successful_requests (for testing)."""
        if self.total_requests == 0:
            self.total_requests = 100  # Default for testing
        self.successful_requests = int(value * self.total_requests)
    
    def update_metrics(self, success: bool, response_time: float, error: str | None = None) -> None:
        """Update provider metrics with new request data."""
        self.total_requests += 1
        self.last_used = datetime.now()
        
        if success:
            self.successful_requests += 1
            self.consecutive_failures = 0
            self.last_error = None
        else:
            self.consecutive_failures += 1
            self.last_error = error
        
        # Update moving averages (exponential smoothing)
        alpha = 0.1  # Smoothing factor
        if self.total_requests == 1:
            self.avg_response_time = response_time
            self.recent_response_time = response_time
            self.recent_success_rate = 1.0 if success else 0.0
        else:
            self.avg_response_time = (
                (1 - alpha) * self.avg_response_time + alpha * response_time
            )
            self.recent_response_time = (
                (1 - alpha) * self.recent_response_time + alpha * response_time
            )
            self.recent_success_rate = (
                (1 - alpha) * self.recent_success_rate + alpha * (1.0 if success else 0.0)
            )


class DataRouter:
    """
    Intelligent data router for selecting optimal data providers.
    
    The DataRouter implements sophisticated provider selection logic
    based on multiple factors including performance, availability,
    and query requirements. It supports various routing strategies
    and includes health monitoring and load balancing capabilities.
    """
    
    def __init__(
        self,
        registry: ProviderRegistry,
        routing_strategy: RoutingStrategy = RoutingStrategy.INTELLIGENT,
        health_check_interval: int = 300,  # 5 minutes
        max_concurrent_health_checks: int = 10,
        enable_caching: bool = True,
        score_decay_factor: float = 0.95,  # For aging old scores
    ) -> None:
        """
        Initialize the DataRouter.
        
        Args:
            registry: Provider registry instance
            routing_strategy: Strategy for provider selection
            health_check_interval: Interval between health checks (seconds)
            max_concurrent_health_checks: Max concurrent health checks
            enable_caching: Whether to cache health check results
            score_decay_factor: Factor for aging provider scores
        """
        self.registry = registry
        self.routing_strategy = routing_strategy
        self.health_check_interval = health_check_interval
        self.max_concurrent_health_checks = max_concurrent_health_checks
        self.enable_caching = enable_caching
        self.score_decay_factor = score_decay_factor
        
        # Provider performance tracking
        self._provider_scores: dict[str, ProviderScore] = {}
        self._provider_health_cache: dict[str, dict[str, Any]] = {}
        
        # Round-robin state
        self._round_robin_index = 0
        
        # Background tasks
        self._health_check_task: asyncio.Task | None = None
        self._score_decay_task: asyncio.Task | None = None
    
    def register_provider(self, provider: DataProvider, config: dict[str, Any] | None = None) -> None:
        """
        Register a data provider with the router.
        
        Args:
            provider: The data provider to register
            config: Optional configuration for the provider
        """
        self.registry.register_provider(provider, config)
        self._provider_scores[provider.name] = ProviderScore(provider)
        logger.info(f"Registered provider with router: {provider.name}")
    
    def unregister_provider(self, provider_name: str) -> bool:
        """
        Unregister a data provider from the router.
        
        Args:
            provider_name: Name of the provider to unregister
            
        Returns:
            bool: True if provider was unregistered, False if not found
        """
        result = self.registry.unregister_provider(provider_name)
        if result:
            self._provider_scores.pop(provider_name, None)
            self._provider_health_cache.pop(provider_name, None)
            logger.info(f"Unregistered provider from router: {provider_name}")
        return result
    
    def get_available_providers(self, query: DataQuery) -> list[DataProvider]:
        """
        Get all providers that can handle the given query and are healthy.
        
        Args:
            query: The data query to match against
            
        Returns:
            List of available providers
        """
        compatible_providers = self.registry.find_providers(query)
        
        # Filter out unhealthy providers
        healthy_providers = []
        for provider in compatible_providers:
            if self._is_provider_healthy_cached(provider):
                healthy_providers.append(provider)
        
        return healthy_providers
    
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
        # Check for preferred provider in query
        if query.provider:
            preferred_provider = self.registry.get_provider(query.provider)
            if preferred_provider and preferred_provider.can_handle_query(query):
                if await self._is_provider_healthy(preferred_provider):
                    logger.debug(f"Using preferred provider: {query.provider}")
                    return preferred_provider
                else:
                    logger.warning(f"Preferred provider {query.provider} is unhealthy, falling back")
        
        # Get available providers
        available_providers = self.get_available_providers(query)
        
        if not available_providers:
            attempted_providers = [p.name for p in self.registry.find_providers(query)]
            raise NoAvailableProviderException(
                "No available provider for request",
                query=query.cache_key(),
                attempted_providers=attempted_providers,
                details={
                    "asset": query.asset.value,
                    "market": query.market.value if query.market else None,
                    "provider_count": len(attempted_providers),
                },
            )
        
        # Select provider based on strategy
        selected_provider = await self._select_provider(available_providers, query)
        
        # Update provider score for selection (simulated successful routing)
        await self._update_provider_score(
            selected_provider.name,
            success=True,
            response_time=0.01,  # Minimal time for routing
            error=None,
        )
        
        logger.debug(
            f"Selected provider {selected_provider.name} for query "
            f"(strategy: {self.routing_strategy.value})"
        )
        
        return selected_provider
    
    async def _select_provider(self, providers: list[DataProvider], query: DataQuery) -> DataProvider:
        """
        Select a provider from the available list based on routing strategy.
        
        Args:
            providers: List of available providers
            query: The data query context
            
        Returns:
            Selected DataProvider
        """
        if len(providers) == 1:
            return providers[0]
        
        if self.routing_strategy == RoutingStrategy.INTELLIGENT:
            return await self._select_intelligent(providers, query)
        elif self.routing_strategy == RoutingStrategy.ROUND_ROBIN:
            return self._select_round_robin(providers)
        elif self.routing_strategy == RoutingStrategy.RANDOM:
            return self._select_random(providers)
        elif self.routing_strategy == RoutingStrategy.WEIGHTED:
            return await self._select_weighted(providers, query)
        else:
            # Default to intelligent
            return await self._select_intelligent(providers, query)
    
    async def _select_intelligent(self, providers: list[DataProvider], query: DataQuery) -> DataProvider:
        """Select provider using intelligent scoring algorithm."""
        best_provider = None
        best_score = -1.0
        
        for provider in providers:
            score = self._calculate_provider_score(
                success_rate=self._provider_scores[provider.name].recent_success_rate,
                avg_response_time=self._provider_scores[provider.name].recent_response_time,
                total_requests=self._provider_scores[provider.name].total_requests,
            )
            
            if score > best_score:
                best_score = score
                best_provider = provider
        
        return best_provider or providers[0]
    
    def _select_round_robin(self, providers: list[DataProvider]) -> DataProvider:
        """Select provider using round-robin algorithm."""
        provider = providers[self._round_robin_index % len(providers)]
        self._round_robin_index += 1
        return provider
    
    def _select_random(self, providers: list[DataProvider]) -> DataProvider:
        """Select provider randomly."""
        return random.choice(providers)
    
    async def _select_weighted(self, providers: list[DataProvider], query: DataQuery) -> DataProvider:
        """Select provider using weighted random selection based on scores."""
        weights = []
        for provider in providers:
            score = self._calculate_provider_score(
                success_rate=self._provider_scores[provider.name].recent_success_rate,
                avg_response_time=self._provider_scores[provider.name].recent_response_time,
                total_requests=self._provider_scores[provider.name].total_requests,
            )
            weights.append(max(score, 0.1))  # Minimum weight to avoid zero
        
        # Weighted random selection
        total_weight = sum(weights)
        if total_weight == 0:
            return random.choice(providers)
        
        r = random.uniform(0, total_weight)
        cumulative_weight = 0
        
        for i, weight in enumerate(weights):
            cumulative_weight += weight
            if r <= cumulative_weight:
                return providers[i]
        
        return providers[-1]  # Fallback
    
    def _calculate_provider_score(
        self,
        success_rate: float,
        avg_response_time: float,
        total_requests: int,
    ) -> float:
        """
        Calculate a composite score for provider selection.
        
        Args:
            success_rate: Provider success rate (0.0-1.0)
            avg_response_time: Average response time in seconds
            total_requests: Total number of requests made
            
        Returns:
            Composite score (higher is better)
        """
        # Base score from success rate (0-100)
        score = success_rate * 100
        
        # Penalty for slow response times
        if avg_response_time > 0:
            # Logarithmic penalty for response time
            time_penalty = min(50, 10 * (avg_response_time ** 0.5))
            score -= time_penalty
        
        # Bonus for providers with more experience (up to 20 points)
        experience_bonus = min(20, total_requests / 100)
        score += experience_bonus
        
        # Ensure score is non-negative
        return max(0.0, score)
    
    async def _is_provider_healthy(self, provider: DataProvider) -> bool:
        """
        Check if a provider is healthy, using cache if enabled.
        
        Args:
            provider: Provider to check
            
        Returns:
            bool: True if provider is healthy
        """
        if not self.enable_caching:
            return await self._check_provider_health(provider)
        
        provider_name = provider.name
        now = datetime.now()
        
        # Check cache
        if provider_name in self._provider_health_cache:
            cache_entry = self._provider_health_cache[provider_name]
            last_check = cache_entry["last_check"]
            
            # Use cached result if not expired
            if (now - last_check).total_seconds() < self.health_check_interval:
                return cache_entry["is_healthy"]
        
        # Perform health check and cache result
        is_healthy = await self._check_provider_health(provider)
        self._provider_health_cache[provider_name] = {
            "is_healthy": is_healthy,
            "last_check": now,
        }
        
        return is_healthy
    
    def _is_provider_healthy_cached(self, provider: DataProvider) -> bool:
        """
        Check provider health using only cached data (non-async).
        
        Args:
            provider: Provider to check
            
        Returns:
            bool: True if provider is healthy (defaults to True if no cache)
        """
        if not self.enable_caching:
            return True  # Assume healthy if caching disabled
        
        provider_name = provider.name
        
        if provider_name in self._provider_health_cache:
            cache_entry = self._provider_health_cache[provider_name]
            now = datetime.now()
            last_check = cache_entry["last_check"]
            
            # Use cached result if not too old
            if (now - last_check).total_seconds() < self.health_check_interval * 2:
                return cache_entry["is_healthy"]
        
        return True  # Default to healthy if no recent cache
    
    async def _check_provider_health(self, provider: DataProvider) -> bool:
        """
        Perform actual health check on a provider.
        
        Args:
            provider: Provider to check
            
        Returns:
            bool: True if provider is healthy
        """
        try:
            start_time = datetime.now()
            is_healthy = await provider.health_check()
            end_time = datetime.now()
            
            response_time = (end_time - start_time).total_seconds()
            
            # Cache the health check result
            if self.enable_caching:
                self._provider_health_cache[provider.name] = {
                    "is_healthy": is_healthy,
                    "last_check": datetime.now(),
                }
            
            # Update provider score with health check result
            await self._update_provider_score(
                provider.name,
                success=is_healthy,
                response_time=response_time,
                error=None if is_healthy else "Health check failed",
            )
            
            return is_healthy
            
        except Exception as e:
            logger.warning(f"Health check failed for provider {provider.name}: {e}")
            
            # Cache the failure result
            if self.enable_caching:
                self._provider_health_cache[provider.name] = {
                    "is_healthy": False,
                    "last_check": datetime.now(),
                }
            
            # Update provider score with failure
            await self._update_provider_score(
                provider.name,
                success=False,
                response_time=0.0,
                error=str(e),
            )
            
            return False
    
    async def check_all_provider_health(self) -> dict[str, bool]:
        """
        Check health of all registered providers.
        
        Returns:
            Dictionary mapping provider names to health status
        """
        providers = list(self.registry.get_all_providers().values())
        
        # Limit concurrent health checks
        semaphore = asyncio.Semaphore(self.max_concurrent_health_checks)
        
        async def check_with_semaphore(provider: DataProvider) -> tuple[str, bool]:
            async with semaphore:
                is_healthy = await self._check_provider_health(provider)
                return provider.name, is_healthy
        
        # Execute health checks concurrently
        tasks = [check_with_semaphore(provider) for provider in providers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        health_status = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Health check task failed: {result}")
                continue
            
            provider_name, is_healthy = result
            health_status[provider_name] = is_healthy
        
        logger.info(f"Health check completed for {len(health_status)} providers")
        return health_status
    
    async def _update_provider_score(
        self,
        provider_name: str,
        success: bool,
        response_time: float,
        error: str | None = None,
    ) -> None:
        """
        Update provider performance score.
        
        Args:
            provider_name: Name of the provider
            success: Whether the request was successful
            response_time: Response time in seconds
            error: Error message if request failed
        """
        if provider_name not in self._provider_scores:
            return
        
        score = self._provider_scores[provider_name]
        score.update_metrics(success, response_time, error)
        
        logger.debug(
            f"Updated score for {provider_name}: "
            f"success_rate={score.success_rate:.3f}, "
            f"avg_response_time={score.avg_response_time:.3f}s, "
            f"total_requests={score.total_requests}"
        )
    
    def get_provider_statistics(self) -> dict[str, Any]:
        """
        Get comprehensive statistics about all providers.
        
        Returns:
            Dictionary containing provider statistics
        """
        stats = {
            "total_providers": len(self._provider_scores),
            "routing_strategy": self.routing_strategy.value,
            "health_check_interval": self.health_check_interval,
            "providers": {},
        }
        
        for provider_name, score in self._provider_scores.items():
            provider_stats = {
                "total_requests": score.total_requests,
                "successful_requests": score.successful_requests,
                "success_rate": score.success_rate,
                "avg_response_time": score.avg_response_time,
                "recent_success_rate": score.recent_success_rate,
                "recent_response_time": score.recent_response_time,
                "consecutive_failures": score.consecutive_failures,
                "last_used": score.last_used.isoformat() if score.last_used else None,
                "last_error": score.last_error,
            }
            
            # Add health status if available
            if provider_name in self._provider_health_cache:
                health_cache = self._provider_health_cache[provider_name]
                provider_stats["is_healthy"] = health_cache["is_healthy"]
                provider_stats["last_health_check"] = health_cache["last_check"].isoformat()
            
            stats["providers"][provider_name] = provider_stats
        
        return stats
    
    async def start_background_tasks(self) -> None:
        """Start background tasks for health monitoring and score maintenance."""
        if self._health_check_task is None:
            self._health_check_task = asyncio.create_task(self._periodic_health_check())
        
        if self._score_decay_task is None:
            self._score_decay_task = asyncio.create_task(self._periodic_score_decay())
        
        logger.info("Started DataRouter background tasks")
    
    async def stop_background_tasks(self) -> None:
        """Stop background tasks."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
        
        if self._score_decay_task:
            self._score_decay_task.cancel()
            try:
                await self._score_decay_task
            except asyncio.CancelledError:
                pass
            self._score_decay_task = None
        
        logger.info("Stopped DataRouter background tasks")
    
    async def _periodic_health_check(self) -> None:
        """Periodic health check background task."""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                await self.check_all_provider_health()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic health check: {e}")
    
    async def _periodic_score_decay(self) -> None:
        """Periodic score decay background task to age old performance data."""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                
                for score in self._provider_scores.values():
                    # Decay recent metrics to give more weight to current performance
                    score.recent_success_rate = (
                        score.recent_success_rate * self.score_decay_factor +
                        score.success_rate * (1 - self.score_decay_factor)
                    )
                    score.recent_response_time = (
                        score.recent_response_time * self.score_decay_factor +
                        score.avg_response_time * (1 - self.score_decay_factor)
                    )
                
                logger.debug("Applied score decay to provider metrics")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic score decay: {e}")