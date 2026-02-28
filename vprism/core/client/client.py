"""vprism main client - synchronous and asynchronous API."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from datetime import datetime
from typing import Any

from vprism.core.client.builder import QueryBuilder
from vprism.core.config.settings import ConfigManager, load_config_from_env
from vprism.core.models.market import AssetType, MarketType, TimeFrame
from vprism.core.models.query import DataQuery
from vprism.core.models.response import DataResponse


class VPrismClient:
    """vprism main client - synchronous and asynchronous financial data access."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the client.

        Args:
            config: Optional configuration dictionary.
        """
        self.config_manager = ConfigManager()

        env_config = load_config_from_env()
        if env_config:
            self.config_manager.update_config(**env_config)

        if config:
            self.config_manager.update_config(**config)

        from vprism.core.data.providers.registry import ProviderRegistry
        from vprism.core.data.routing import DataRouter

        self.registry = ProviderRegistry()
        self.router = DataRouter(self.registry)
        self._configured = True
        self._apply_config()

    def configure(self, **config: Any) -> None:
        """Update client configuration.

        Args:
            **config: Configuration key-value pairs.
        """
        self.config_manager.update_config(**config)
        self._apply_config()

    def _apply_config(self) -> None:
        """Apply configuration to components."""
        from vprism.core.data.providers.factory import create_default_providers

        if len(self.registry) == 0:
            providers = create_default_providers()
            for _name, provider in providers.items():
                self.registry.register(provider)
            self.router.refresh_scores()

    def query(self) -> QueryBuilder:
        """Get a query builder instance."""
        return QueryBuilder()

    async def execute(self, query: DataQuery) -> DataResponse:
        """Execute a data query.

        Args:
            query: The query to execute.

        Returns:
            DataResponse with the query results.
        """
        if not self._configured:
            self._apply_config()

        provider = await self.router.route_query(query)
        response: DataResponse = await provider.get_data(query)
        return response

    def get(
        self,
        asset: str | AssetType,
        market: str | MarketType | None = None,
        symbols: list[str] | None = None,
        timeframe: str | TimeFrame | None = None,
        start: str | None = None,
        end: str | None = None,
        provider: str | None = None,
        **kwargs: Any,
    ) -> DataResponse:
        """Synchronous data access API.

        Args:
            asset: Asset type (stock, etf, crypto, etc.)
            market: Market identifier (cn, us, hk, etc.)
            symbols: List of ticker symbols.
            timeframe: Data timeframe (1d, 1h, 5m, etc.)
            start: Start date YYYY-MM-DD.
            end: End date YYYY-MM-DD.
            provider: Preferred provider name.
            **kwargs: Additional parameters.

        Returns:
            DataResponse containing financial data.
        """
        start_dt = datetime.fromisoformat(start) if start else None
        end_dt = datetime.fromisoformat(end) if end else None

        asset_type = AssetType(asset) if isinstance(asset, str) else asset
        market_type = MarketType(market) if isinstance(market, str) else market
        tf = TimeFrame(timeframe) if isinstance(timeframe, str) else (timeframe or TimeFrame.DAY_1)

        query = DataQuery(
            asset=asset_type,
            market=market_type,
            symbols=symbols,
            timeframe=tf,
            start=start_dt,
            end=end_dt,
            provider=provider,
        )

        return self._run_sync(self.execute(query))

    async def get_async(
        self,
        asset: str | AssetType,
        market: str | MarketType | None = None,
        symbols: list[str] | None = None,
        timeframe: str | TimeFrame | None = None,
        start: str | None = None,
        end: str | None = None,
        provider: str | None = None,
        **kwargs: Any,
    ) -> DataResponse:
        """Asynchronous data access API.

        Args:
            asset: Asset type.
            market: Market identifier.
            symbols: List of ticker symbols.
            timeframe: Data timeframe.
            start: Start date YYYY-MM-DD.
            end: End date YYYY-MM-DD.
            provider: Preferred provider name.
            **kwargs: Additional parameters.

        Returns:
            DataResponse containing financial data.
        """
        start_dt = datetime.fromisoformat(start) if start else None
        end_dt = datetime.fromisoformat(end) if end else None

        asset_type = AssetType(asset) if isinstance(asset, str) else asset
        market_type = MarketType(market) if isinstance(market, str) else market
        tf = TimeFrame(timeframe) if isinstance(timeframe, str) else (timeframe or TimeFrame.DAY_1)

        query = DataQuery(
            asset=asset_type,
            market=market_type,
            symbols=symbols,
            timeframe=tf,
            start=start_dt,
            end=end_dt,
            provider=provider,
        )

        return await self.execute(query)

    def _run_sync(self, coro: Coroutine[Any, Any, DataResponse]) -> DataResponse:
        """Run an async coroutine synchronously.

        Uses asyncio.run() as primary strategy with nest_asyncio fallback
        for environments with an already-running event loop.
        """
        try:
            # Try get_running_loop first to detect if we're inside an event loop
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop - safe to use asyncio.run()
            return asyncio.run(coro)

        # We're inside a running loop - use nest_asyncio to allow nesting
        import nest_asyncio  # type: ignore[import-untyped]

        nest_asyncio.apply()
        return loop.run_until_complete(coro)
