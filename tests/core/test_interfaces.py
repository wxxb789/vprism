"""
Tests for core interfaces and abstract base classes.

This module contains tests for all interface contracts and abstract base classes,
ensuring proper implementation requirements and behavior.
"""

from abc import ABC
from collections.abc import AsyncIterator
from unittest.mock import MagicMock

import pytest

from vprism.core.interfaces import (
    CacheRepository,
    DataProvider,
    DataRepository,
    DataRouter,
    EventPublisher,
    MetricsCollector,
)
from vprism.core.models import AssetType, DataPoint, DataQuery, DataResponse


class TestDataProviderInterface:
    """Test DataProvider abstract base class."""

    def test_data_provider_is_abstract(self):
        """Test that DataProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            DataProvider()

    def test_data_provider_abstract_methods(self):
        """Test that DataProvider has required abstract methods."""
        abstract_methods = DataProvider.__abstractmethods__
        expected_methods = {
            "name",
            "info",
            "supported_assets",
            "get_data",
            "stream_data",
            "health_check",
            "can_handle_query",
        }
        assert abstract_methods == expected_methods

    def test_concrete_data_provider_implementation(self):
        """Test that concrete implementation works correctly."""

        class ConcreteDataProvider(DataProvider):
            @property
            def name(self) -> str:
                return "test_provider"

            @property
            def info(self):
                return MagicMock()

            @property
            def supported_assets(self) -> set[AssetType]:
                return {AssetType.STOCK}

            async def get_data(self, query: DataQuery) -> DataResponse:
                return MagicMock()

            async def stream_data(self, query: DataQuery) -> AsyncIterator[DataPoint]:
                yield MagicMock()

            async def health_check(self) -> bool:
                return True

            def can_handle_query(self, query: DataQuery) -> bool:
                return True

        # Should be able to instantiate concrete implementation
        provider = ConcreteDataProvider()
        assert provider.name == "test_provider"
        assert AssetType.STOCK in provider.supported_assets


class TestCacheRepositoryInterface:
    """Test CacheRepository abstract base class."""

    def test_cache_repository_is_abstract(self):
        """Test that CacheRepository cannot be instantiated directly."""
        with pytest.raises(TypeError):
            CacheRepository()

    def test_cache_repository_abstract_methods(self):
        """Test that CacheRepository has required abstract methods."""
        abstract_methods = CacheRepository.__abstractmethods__
        expected_methods = {"get", "set", "delete", "clear", "exists"}
        assert abstract_methods == expected_methods

    def test_concrete_cache_repository_implementation(self):
        """Test that concrete implementation works correctly."""

        class ConcreteCacheRepository(CacheRepository):
            async def get(self, key: str):
                return None

            async def set(self, key: str, value, ttl=None) -> None:
                pass

            async def delete(self, key: str) -> bool:
                return True

            async def clear(self) -> None:
                pass

            async def exists(self, key: str) -> bool:
                return False

        # Should be able to instantiate concrete implementation
        cache = ConcreteCacheRepository()
        assert cache is not None


class TestDataRepositoryInterface:
    """Test DataRepository abstract base class."""

    def test_data_repository_is_abstract(self):
        """Test that DataRepository cannot be instantiated directly."""
        with pytest.raises(TypeError):
            DataRepository()

    def test_data_repository_abstract_methods(self):
        """Test that DataRepository has required abstract methods."""
        abstract_methods = DataRepository.__abstractmethods__
        expected_methods = {"store_data", "retrieve_data", "delete_data"}
        assert abstract_methods == expected_methods

    def test_concrete_data_repository_implementation(self):
        """Test that concrete implementation works correctly."""

        class ConcreteDataRepository(DataRepository):
            async def store_data(self, data):
                pass

            async def retrieve_data(self, query):
                return []

            async def delete_data(self, query):
                return 0

        # Should be able to instantiate concrete implementation
        repo = ConcreteDataRepository()
        assert repo is not None


class TestDataRouterInterface:
    """Test DataRouter abstract base class."""

    def test_data_router_is_abstract(self):
        """Test that DataRouter cannot be instantiated directly."""
        with pytest.raises(TypeError):
            DataRouter()

    def test_data_router_abstract_methods(self):
        """Test that DataRouter has required abstract methods."""
        abstract_methods = DataRouter.__abstractmethods__
        expected_methods = {
            "route_query",
            "register_provider",
            "unregister_provider",
            "get_available_providers",
        }
        assert abstract_methods == expected_methods

    def test_concrete_data_router_implementation(self):
        """Test that concrete implementation works correctly."""

        class ConcreteDataRouter(DataRouter):
            async def route_query(self, query):
                return MagicMock()

            def register_provider(self, provider) -> None:
                pass

            def unregister_provider(self, provider_name: str) -> bool:
                return True

            def get_available_providers(self, query):
                return []

        # Should be able to instantiate concrete implementation
        router = ConcreteDataRouter()
        assert router is not None


class TestEventPublisherInterface:
    """Test EventPublisher abstract base class."""

    def test_event_publisher_is_abstract(self):
        """Test that EventPublisher cannot be instantiated directly."""
        with pytest.raises(TypeError):
            EventPublisher()

    def test_event_publisher_abstract_methods(self):
        """Test that EventPublisher has required abstract methods."""
        abstract_methods = EventPublisher.__abstractmethods__
        expected_methods = {"publish", "subscribe"}
        assert abstract_methods == expected_methods

    def test_concrete_event_publisher_implementation(self):
        """Test that concrete implementation works correctly."""

        class ConcreteEventPublisher(EventPublisher):
            async def publish(self, event_type: str, data):
                pass

            async def subscribe(self, event_type: str, callback):
                pass

        # Should be able to instantiate concrete implementation
        publisher = ConcreteEventPublisher()
        assert publisher is not None


class TestMetricsCollectorInterface:
    """Test MetricsCollector abstract base class."""

    def test_metrics_collector_is_abstract(self):
        """Test that MetricsCollector cannot be instantiated directly."""
        with pytest.raises(TypeError):
            MetricsCollector()

    def test_metrics_collector_abstract_methods(self):
        """Test that MetricsCollector has required abstract methods."""
        abstract_methods = MetricsCollector.__abstractmethods__
        expected_methods = {"increment_counter", "record_histogram", "set_gauge"}
        assert abstract_methods == expected_methods

    def test_concrete_metrics_collector_implementation(self):
        """Test that concrete implementation works correctly."""

        class ConcreteMetricsCollector(MetricsCollector):
            def increment_counter(self, name: str, value: float = 1.0, tags=None):
                pass

            def record_histogram(self, name: str, value: float, tags=None):
                pass

            def set_gauge(self, name: str, value: float, tags=None):
                pass

        # Should be able to instantiate concrete implementation
        collector = ConcreteMetricsCollector()
        assert collector is not None


class TestInterfaceInheritance:
    """Test interface inheritance and relationships."""

    def test_all_interfaces_are_abstract(self):
        """Test that all interfaces are abstract base classes."""
        interfaces = [
            DataProvider,
            CacheRepository,
            DataRepository,
            DataRouter,
            EventPublisher,
            MetricsCollector,
        ]

        for interface in interfaces:
            assert issubclass(interface, ABC)
            assert len(interface.__abstractmethods__) > 0

    def test_interface_method_signatures(self):
        """Test that interface methods have proper signatures."""
        # This test ensures that interface methods are properly defined
        # and can be used for type checking and documentation

        # DataProvider methods
        assert hasattr(DataProvider, "get_data")
        assert hasattr(DataProvider, "stream_data")
        assert hasattr(DataProvider, "health_check")
        assert hasattr(DataProvider, "can_handle_query")

        # CacheRepository methods
        assert hasattr(CacheRepository, "get")
        assert hasattr(CacheRepository, "set")
        assert hasattr(CacheRepository, "delete")
        assert hasattr(CacheRepository, "clear")
        assert hasattr(CacheRepository, "exists")

        # DataRepository methods
        assert hasattr(DataRepository, "store_data")
        assert hasattr(DataRepository, "retrieve_data")
        assert hasattr(DataRepository, "delete_data")

        # DataRouter methods
        assert hasattr(DataRouter, "route_query")
        assert hasattr(DataRouter, "register_provider")
        assert hasattr(DataRouter, "unregister_provider")
        assert hasattr(DataRouter, "get_available_providers")

        # EventPublisher methods
        assert hasattr(EventPublisher, "publish")
        assert hasattr(EventPublisher, "subscribe")

        # MetricsCollector methods
        assert hasattr(MetricsCollector, "increment_counter")
        assert hasattr(MetricsCollector, "record_histogram")
        assert hasattr(MetricsCollector, "set_gauge")
