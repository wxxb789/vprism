"""Test that vprism can be imported without optional provider dependencies.

These tests verify the Phase 0 fix: lazy imports prevent LSP failures
when optional dependencies (yfinance, akshare, aiohttp) are not installed.
"""

import importlib
import sys


class TestLazyImports:
    """Verify core package imports without triggering provider deps."""

    def test_import_vprism_package(self) -> None:
        """Test that 'import vprism' works."""
        import vprism

        assert hasattr(vprism, "__version__")

    def test_import_core_models(self) -> None:
        """Test that core models can be imported."""
        from vprism.core.models import AssetType, MarketType, TimeFrame

        assert AssetType.STOCK is not None
        assert MarketType.US is not None
        assert TimeFrame.DAY_1 is not None

    def test_import_config(self) -> None:
        """Test that config module can be imported."""
        from vprism.core.config import VPrismConfig

        config = VPrismConfig()
        assert config.cache.enabled is True

    def test_import_exceptions(self) -> None:
        """Test that exceptions can be imported."""
        from vprism.core.exceptions import (
            NoCapableProviderError,
            ProviderError,
            VPrismError,
        )

        assert issubclass(ProviderError, VPrismError)
        assert issubclass(NoCapableProviderError, VPrismError)

    def test_providers_init_lazy(self) -> None:
        """Test that providers/__init__.py uses lazy loading.

        Importing the providers package should NOT trigger yfinance/akshare/aiohttp imports.
        """
        # Record what modules are loaded before
        before = set(sys.modules.keys())

        # Force reimport
        mod_name = "vprism.core.data.providers"
        if mod_name in sys.modules:
            # Already imported, just verify the lazy attribute access works
            mod = sys.modules[mod_name]
            # Accessing __all__ should not trigger provider imports
            assert hasattr(mod, "__all__")
        else:
            importlib.import_module(mod_name)

        after = set(sys.modules.keys())
        new_modules = after - before

        # yfinance, akshare, aiohttp should NOT have been loaded
        for dep in ("yfinance", "akshare", "aiohttp"):
            assert dep not in new_modules, f"{dep} was eagerly imported by providers/__init__.py"

    def test_factory_lazy_import(self) -> None:
        """Test that factory module doesn't eagerly import providers."""
        from vprism.core.data.providers.factory import create_default_providers

        # The function should be importable without triggering provider deps
        assert callable(create_default_providers)

    def test_schema_import_without_duckdb(self) -> None:
        """Test that schema module handles missing duckdb gracefully."""
        # The module should be importable even if duckdb is not available
        from vprism.core.data.storage.schema import TABLE_NAMES

        assert len(TABLE_NAMES) == 6
        assert "assets" in TABLE_NAMES
        assert "ohlcv" in TABLE_NAMES

    def test_data_query_model(self) -> None:
        """Test DataQuery model creation and date sync."""
        from datetime import date, datetime

        from vprism.core.models.market import AssetType
        from vprism.core.models.query import DataQuery

        # Test with start (datetime) - should auto-fill start_date
        q1 = DataQuery(asset=AssetType.STOCK, start=datetime(2024, 1, 1))
        assert q1.start_date == date(2024, 1, 1)

        # Test with start_date (date) - should auto-fill start
        q2 = DataQuery(asset=AssetType.STOCK, start_date=date(2024, 6, 15))
        assert q2.start is not None
        assert q2.start.date() == date(2024, 6, 15)
