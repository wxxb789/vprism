from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from typer.testing import CliRunner

from vprism.cli import data as data_module
from vprism.cli.main import create_app
from vprism.core.models.base import DataPoint
from vprism.core.models.market import AssetType, MarketType, TimeFrame
from vprism.core.models.response import DataResponse, ProviderInfo, ResponseMetadata
from vprism.core.services.symbol_normalization import NormalizedSymbol


class StubDataService:
    def __init__(self, response: DataResponse) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    async def get(
        self,
        *,
        symbols: list[str],
        start: str | None,
        end: str | None,
        market: MarketType,
        asset_type: AssetType,
        timeframe: TimeFrame,
    ) -> DataResponse:
        self.calls.append(
            {
                "symbols": symbols,
                "start": start,
                "end": end,
                "market": market,
                "asset_type": asset_type,
                "timeframe": timeframe,
            }
        )
        return self.response


class StubNormalizer:
    def __init__(self, unresolved: set[str] | None = None) -> None:
        self.unresolved = unresolved or set()

    async def normalize(self, symbols: list[str], market: MarketType | None = None, **_: object) -> list[NormalizedSymbol]:
        results: list[NormalizedSymbol] = []
        for symbol in symbols:
            results.append(
                NormalizedSymbol(
                    raw=symbol,
                    c_symbol=symbol,
                    market=market or MarketType.CN,
                    confidence=1.0,
                    rule="stub",
                    unresolved=symbol in self.unresolved,
                )
            )
        return results


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _build_response() -> DataResponse:
    point = DataPoint(
        symbol="000001",
        market=MarketType.CN,
        timestamp=datetime(2024, 1, 1),
        open_price=Decimal("10.5"),
        high_price=Decimal("11.0"),
        low_price=Decimal("10.0"),
        close_price=Decimal("10.8"),
        volume=Decimal("1000"),
    )
    metadata = ResponseMetadata(total_records=1, query_time_ms=12.5, data_source="stub", cache_hit=False)
    provider = ProviderInfo(name="stub-provider")
    return DataResponse(data=[point], metadata=metadata, source=provider)


def test_fetch_table_output(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    response = _build_response()
    service = StubDataService(response)
    normalizer = StubNormalizer()
    monkeypatch.setattr(data_module, "get_data_service", lambda: service)
    monkeypatch.setattr(data_module, "get_symbol_normalizer", lambda: normalizer)

    app = create_app()
    result = runner.invoke(app, ["data", "fetch", "--symbols", "000001"])

    assert result.exit_code == 0, result.output
    assert "000001" in result.output
    assert "open_price" in result.output
    assert service.calls[0]["symbols"] == ["000001"]
    assert service.calls[0]["timeframe"] == TimeFrame.DAY_1


def test_fetch_jsonl_output(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    response = _build_response()
    service = StubDataService(response)
    normalizer = StubNormalizer()
    monkeypatch.setattr(data_module, "get_data_service", lambda: service)
    monkeypatch.setattr(data_module, "get_symbol_normalizer", lambda: normalizer)

    app = create_app()
    result = runner.invoke(
        app,
        ["--format", "jsonl", "data", "fetch", "--symbols", "000001"],
    )

    assert result.exit_code == 0, result.output
    assert result.output.strip().startswith("{\"symbol\": \"000001\"")
    assert "open_price" in result.output


def test_fetch_reports_unresolved_symbol(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    response = _build_response()
    service = StubDataService(response)
    normalizer = StubNormalizer({"BAD"})
    monkeypatch.setattr(data_module, "get_data_service", lambda: service)
    monkeypatch.setattr(data_module, "get_symbol_normalizer", lambda: normalizer)

    app = create_app()
    result = runner.invoke(app, ["data", "fetch", "--symbols", "BAD"])

    assert result.exit_code == 10
    assert "SYMBOL_UNRESOLVED" in result.output
    assert "BAD" in result.output
    assert service.calls == []
