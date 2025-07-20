"""
Data provider implementations for vprism.

This package contains concrete implementations of data providers
for various financial data sources including akshare, yfinance,
Alpha Vantage, and vprism native providers.
"""

# Import providers with error handling for optional dependencies
try:
    from .akshare_provider import AkshareProvider
    _AKSHARE_AVAILABLE = True
except ImportError:
    _AKSHARE_AVAILABLE = False

try:
    from .yfinance_provider import YfinanceProvider
    _YFINANCE_AVAILABLE = True
except ImportError:
    _YFINANCE_AVAILABLE = False

try:
    from .alpha_vantage_provider import AlphaVantageProvider
    _ALPHA_VANTAGE_AVAILABLE = True
except ImportError:
    _ALPHA_VANTAGE_AVAILABLE = False

# Build __all__ dynamically based on available providers
__all__ = []

if _AKSHARE_AVAILABLE:
    __all__.append("AkshareProvider")

if _YFINANCE_AVAILABLE:
    __all__.append("YfinanceProvider")

if _ALPHA_VANTAGE_AVAILABLE:
    __all__.append("AlphaVantageProvider")

# Convenience functions
def get_available_providers():
    """Get list of available provider classes."""
    providers = []
    if _AKSHARE_AVAILABLE:
        providers.append(AkshareProvider)
    if _YFINANCE_AVAILABLE:
        providers.append(YfinanceProvider)
    if _ALPHA_VANTAGE_AVAILABLE:
        providers.append(AlphaVantageProvider)
    return providers

def get_provider_availability():
    """Get availability status of all providers."""
    return {
        "akshare": _AKSHARE_AVAILABLE,
        "yfinance": _YFINANCE_AVAILABLE,
        "alpha_vantage": _ALPHA_VANTAGE_AVAILABLE,
    }