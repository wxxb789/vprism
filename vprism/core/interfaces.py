"""
Core interfaces and abstract base classes for vprism.

This module defines the contracts and protocols that different components
of the system must implement, enabling loose coupling and testability.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable
from typing import Any

from vprism.core.models import (
    AssetType,
    DataPoint,
    DataQuery,
    DataResponse,
    ProviderInfo,
)


class DataProvider(ABC):
    """
    Abstract base class for data providers.

    All data providers must implement this interface to be compatible
    with the vprism platform. This ensures consistent behavior across
    different data sources.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name identifier."""
        pass

    @property
    @abstractmethod
    def info(self) -> ProviderInfo:
        """Provider information and metadata."""
        pass

    @property
    @abstractmethod
    def supported_assets(self) -> set[AssetType]:
        """Set of asset types supported by this provider."""
        pass

    @abstractmethod
    async def get_data(self, query: DataQuery) -> DataResponse:
        """
        Retrieve data based on the provided query.

        Args:
            query: The data query specification

        Returns:
            DataResponse containing the requested data

        Raises:
            ProviderException: When provider-specific errors occur
            ValidationException: When query validation fails
        """
        pass

    @abstractmethod
    async def stream_data(self, query: DataQuery) -> AsyncIterator[DataPoint]:
        """
        Stream real-time data based on the provided query.

        Args:
            query: The data query specification

        Yields:
            DataPoint: Individual data points as they become available

        Raises:
            ProviderException: When provider-specific errors occur
            ValidationException: When query validation fails
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the provider is healthy and available.

        Returns:
            bool: True if provider is healthy, False otherwise
        """
        pass

    @abstractmethod
    def can_handle_query(self, query: DataQuery) -> bool:
        """
        Check if this provider can handle the given query.

        Args:
            query: The data query to evaluate

        Returns:
            bool: True if provider can handle the query
        """
        pass


class CacheRepository(ABC):
    """
    Abstract base class for cache implementations.

    Defines the interface for caching data responses to improve
    performance and reduce provider API calls.
    """

    @abstractmethod
    async def get(self, key: str) -> DataResponse | None:
        """
        Retrieve cached data response.

        Args:
            key: Cache key

        Returns:
            Cached DataResponse or None if not found
        """
        pass

    @abstractmethod
    async def set(self, key: str, value: DataResponse, ttl: int | None = None) -> None:
        """
        Store data response in cache.

        Args:
            key: Cache key
            value: DataResponse to cache
            ttl: Time to live in seconds (None for default)
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """
        Delete cached data response.

        Args:
            key: Cache key

        Returns:
            bool: True if key was deleted, False if not found
        """
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all cached data."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            bool: True if key exists
        """
        pass


class DataRepository(ABC):
    """
    Abstract base class for data storage implementations.

    Defines the interface for persistent data storage,
    supporting both historical data and metadata.
    """

    @abstractmethod
    async def store_data(self, data: list[DataPoint]) -> None:
        """
        Store data points persistently.

        Args:
            data: List of data points to store
        """
        pass

    @abstractmethod
    async def retrieve_data(self, query: DataQuery) -> list[DataPoint]:
        """
        Retrieve stored data points.

        Args:
            query: Query specification

        Returns:
            List of matching data points
        """
        pass

    @abstractmethod
    async def delete_data(self, query: DataQuery) -> int:
        """
        Delete stored data points.

        Args:
            query: Query specification for data to delete

        Returns:
            Number of deleted records
        """
        pass


class DataRouter(ABC):
    """
    Abstract base class for data routing implementations.

    Responsible for selecting the best data provider for a given query
    based on various factors like availability, cost, and quality.
    """

    @abstractmethod
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
        pass

    @abstractmethod
    def register_provider(self, provider: DataProvider) -> None:
        """
        Register a new data provider.

        Args:
            provider: The provider to register
        """
        pass

    @abstractmethod
    def unregister_provider(self, provider_name: str) -> bool:
        """
        Unregister a data provider.

        Args:
            provider_name: Name of provider to unregister

        Returns:
            bool: True if provider was unregistered
        """
        pass

    @abstractmethod
    def get_available_providers(self, query: DataQuery) -> list[DataProvider]:
        """
        Get all providers that can handle the query.

        Args:
            query: The data query

        Returns:
            List of compatible providers
        """
        pass


class EventPublisher(ABC):
    """
    Abstract base class for event publishing.

    Enables decoupled communication between system components
    through an event-driven architecture.
    """

    @abstractmethod
    async def publish(self, event_type: str, data: dict[str, Any]) -> None:
        """
        Publish an event.

        Args:
            event_type: Type/topic of the event
            data: Event payload
        """
        pass

    @abstractmethod
    async def subscribe(
        self, event_type: str, callback: Callable[[str, dict[str, Any]], None]
    ) -> None:
        """
        Subscribe to events of a specific type.

        Args:
            event_type: Type/topic to subscribe to
            callback: Function to call when event occurs
        """
        pass


class MetricsCollector(ABC):
    """
    Abstract base class for metrics collection.

    Enables monitoring and observability of the system
    through structured metrics collection.
    """

    @abstractmethod
    def increment_counter(
        self, name: str, value: float = 1.0, tags: dict[str, str] | None = None
    ) -> None:
        """
        Increment a counter metric.

        Args:
            name: Metric name
            value: Value to increment by
            tags: Optional metric tags
        """
        pass

    @abstractmethod
    def record_histogram(
        self, name: str, value: float, tags: dict[str, str] | None = None
    ) -> None:
        """
        Record a histogram value.

        Args:
            name: Metric name
            value: Value to record
            tags: Optional metric tags
        """
        pass

    @abstractmethod
    def set_gauge(
        self, name: str, value: float, tags: dict[str, str] | None = None
    ) -> None:
        """
        Set a gauge metric value.

        Args:
            name: Metric name
            value: Value to set
            tags: Optional metric tags
        """
        pass
