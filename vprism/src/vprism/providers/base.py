"""Base classes for data provider abstraction."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict

from ..models.enums import AssetType, MarketType, TimeFrame, AuthType
from ..models.data import DataQuery, DataResponse


class AuthConfig(BaseModel):
    """Authentication configuration for data providers."""
    
    auth_type: AuthType = Field(..., description="Authentication type")
    config: Dict[str, Any] = Field(default_factory=dict, description="Authentication configuration")
    
    def get_api_key(self) -> Optional[str]:
        """Get API key if auth type is API_KEY."""
        if self.auth_type == AuthType.API_KEY:
            return self.config.get("api_key")
        return None
    
    def get_token(self) -> Optional[str]:
        """Get bearer token if auth type is BEARER_TOKEN."""
        if self.auth_type == AuthType.BEARER_TOKEN:
            return self.config.get("token")
        return None
    
    def get_oauth_config(self) -> Optional[Dict[str, str]]:
        """Get OAuth2 configuration if auth type is OAUTH2."""
        if self.auth_type == AuthType.OAUTH2:
            return {
                "client_id": self.config.get("client_id", ""),
                "client_secret": self.config.get("client_secret", ""),
                "scope": self.config.get("scope", ""),
            }
        return None


class RateLimitConfig(BaseModel):
    """Rate limit configuration for data providers."""
    
    requests_per_minute: Optional[int] = Field(None, description="Requests per minute limit")
    requests_per_hour: Optional[int] = Field(None, description="Requests per hour limit")
    requests_per_day: Optional[int] = Field(None, description="Requests per day limit")
    burst_limit: Optional[int] = Field(None, description="Burst request limit")
    
    def is_limited(self) -> bool:
        """Check if any rate limits are configured."""
        return any([
            self.requests_per_minute is not None,
            self.requests_per_hour is not None,
            self.requests_per_day is not None,
            self.burst_limit is not None,
        ])


class ProviderCapability(BaseModel):
    """Provider capability specification."""
    
    asset_types: List[AssetType] = Field(..., description="Supported asset types")
    markets: List[MarketType] = Field(..., description="Supported markets")
    timeframes: List[TimeFrame] = Field(..., description="Supported time frames")
    supports_real_time: bool = Field(False, description="Supports real-time data")
    supports_historical: bool = Field(True, description="Supports historical data")
    max_symbols_per_request: int = Field(100, description="Maximum symbols per request")
    min_date: Optional[datetime] = Field(None, description="Earliest available date")
    max_date: Optional[datetime] = Field(None, description="Latest available date")
    
    def model_post_init(self, __context):
        """Validate after initialization."""
        if not self.asset_types:
            raise ValueError('asset_types cannot be empty')
        if not self.markets:
            raise ValueError('markets cannot be empty')
        if not self.timeframes:
            raise ValueError('timeframes cannot be empty')
    
    def can_handle_asset_type(self, asset_type: AssetType) -> bool:
        """Check if provider supports the asset type."""
        return asset_type in self.asset_types
    
    def can_handle_market(self, market: MarketType) -> bool:
        """Check if provider supports the market."""
        return market in self.markets
    
    def can_handle_timeframe(self, timeframe: TimeFrame) -> bool:
        """Check if provider supports the time frame."""
        return timeframe in self.timeframes
    
    def is_within_date_range(self, start_date: Optional[datetime], end_date: Optional[datetime]) -> bool:
        """Check if date range is within provider's supported range."""
        if not (start_date or end_date):
            return True
            
        if start_date and self.min_date and start_date < self.min_date:
            return False
            
        if end_date and self.max_date and end_date > self.max_date:
            return False
            
        return True


class DataProvider(ABC):
    """Abstract base class for data providers."""
    
    def __init__(
        self,
        name: str,
        display_name: str,
        capability: ProviderCapability,
        auth_config: AuthConfig,
        rate_limit: Optional[RateLimitConfig] = None,
        description: Optional[str] = None,
        **kwargs
    ):
        """Initialize data provider."""
        self.name = name
        self.display_name = display_name
        self.capability = capability
        self.auth_config = auth_config
        self.rate_limit = rate_limit or RateLimitConfig()
        self.description = description or ""
        self.extra_config = kwargs
    
    @abstractmethod
    async def fetch_data(self, query: DataQuery) -> DataResponse:
        """Fetch data based on query parameters."""
        pass
    
    @abstractmethod
    async def check_health(self) -> Dict[str, Any]:
        """Check provider health status."""
        pass
    
    def can_handle_query(self, query: DataQuery) -> bool:
        """Check if provider can handle the given query."""
        # Check asset type support
        if not self.capability.can_handle_asset_type(query.asset_type):
            return False
        
        # Check market support (if market specified)
        if query.market and not self.capability.can_handle_market(query.market):
            return False
        
        # Check time frame support (if timeframe specified)
        if query.timeframe and not self.capability.can_handle_timeframe(query.timeframe):
            return False
        
        # Check symbol count limits
        if len(query.symbols) > self.capability.max_symbols_per_request:
            return False
        
        # Check date range
        if not self.capability.is_within_date_range(query.start, query.end):
            return False
        
        return True
    
    def get_info(self) -> Dict[str, Any]:
        """Get provider information."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "capability": self.capability.model_dump(),
            "rate_limit": self.rate_limit.model_dump(),
            "auth_type": self.auth_config.auth_type,
        }


class ProviderRegistry:
    """Registry for managing data providers."""
    
    def __init__(self):
        """Initialize empty provider registry."""
        self._providers: Dict[str, DataProvider] = {}
    
    def register(self, provider: DataProvider) -> None:
        """Register a data provider."""
        if not isinstance(provider, DataProvider):
            raise TypeError("Provider must be an instance of DataProvider")
        
        if provider.name in self._providers:
            raise ValueError(f"Provider with name '{provider.name}' already registered")
        
        self._providers[provider.name] = provider
    
    def unregister(self, name: str) -> None:
        """Unregister a data provider."""
        if name not in self._providers:
            raise KeyError(f"Provider '{name}' not found")
        
        del self._providers[name]
    
    def get(self, name: str) -> Optional[DataProvider]:
        """Get provider by name."""
        return self._providers.get(name)
    
    @property
    def providers(self) -> Dict[str, DataProvider]:
        """Get all registered providers."""
        return self._providers.copy()
    
    def list_providers(self) -> Dict[str, DataProvider]:
        """List all registered providers."""
        return self._providers.copy()
    
    def find_suitable_providers(self, query: DataQuery) -> List[DataProvider]:
        """Find providers that can handle the given query."""
        suitable = []
        for provider in self._providers.values():
            if provider.can_handle_query(query):
                suitable.append(provider)
        return suitable
    
    async def check_all_health(self) -> Dict[str, Dict[str, Any]]:
        """Check health of all registered providers."""
        results = {}
        for name, provider in self._providers.items():
            try:
                results[name] = await provider.check_health()
            except Exception as e:
                results[name] = {
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
        return results
    
    def clear(self) -> None:
        """Clear all registered providers."""
        self._providers.clear()
    
    def __len__(self) -> int:
        """Get number of registered providers."""
        return len(self._providers)
    
    def __contains__(self, name: str) -> bool:
        """Check if provider is registered."""
        return name in self._providers
    
    def __iter__(self):
        """Iterate over registered providers."""
        return iter(self._providers.values())