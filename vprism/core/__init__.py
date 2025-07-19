"""
Core domain models and interfaces for vprism.

This module contains the fundamental building blocks of the vprism platform,
including data models, query interfaces, and core abstractions.
"""

from vprism.core.data_router import IntelligentDataRouter
from vprism.core.mock_providers import (
    MockDataProvider,
    AlwaysFailingProvider,
    RateLimitedProvider,
    SlowProvider,
    SpecializedProvider,
    create_test_provider_suite,
)
from vprism.core.provider_registry import (
    ProviderRegistry,
    find_providers,
    get_global_registry,
    register_provider,
    unregister_provider,
)

__all__ = [
    "IntelligentDataRouter",
    "MockDataProvider",
    "AlwaysFailingProvider", 
    "RateLimitedProvider",
    "SlowProvider",
    "SpecializedProvider",
    "create_test_provider_suite",
    "ProviderRegistry",
    "find_providers", 
    "get_global_registry",
    "register_provider",
    "unregister_provider",
]
