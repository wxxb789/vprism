"""Enumerations for vprism data models."""

from enum import Enum


class AssetType(str, Enum):
    """Supported financial asset types."""
    
    STOCK = "stock"
    BOND = "bond"
    ETF = "etf"
    FUND = "fund"
    FUTURES = "futures"
    OPTIONS = "options"
    FOREX = "forex"
    CRYPTO = "crypto"
    INDEX = "index"
    COMMODITY = "commodity"


class MarketType(str, Enum):
    """Supported financial markets."""
    
    CN = "cn"  # China
    US = "us"  # United States
    HK = "hk"  # Hong Kong
    EU = "eu"  # Europe
    JP = "jp"  # Japan
    GLOBAL = "global"


class TimeFrame(str, Enum):
    """Supported time frames for data."""
    
    TICK = "tick"
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"
    WEEK_1 = "1w"
    MONTH_1 = "1M"


class ProviderType(str, Enum):
    """Types of data providers."""
    
    EXCHANGE = "exchange"
    THIRD_PARTY = "third_party"
    AGGREGATOR = "aggregator"
    FREE = "free"
    PAID = "paid"


class DataQuality(str, Enum):
    """Data quality levels."""
    
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class AuthType(str, Enum):
    """Authentication types for providers."""
    
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    BASIC_AUTH = "basic_auth"
    OAUTH2 = "oauth2"
    NONE = "none"