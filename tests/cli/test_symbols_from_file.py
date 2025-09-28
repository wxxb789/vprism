from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from vprism.cli import data as data_module
from vprism.cli.main import create_app
from vprism.core.models.market import AssetType, MarketType, TimeFrame
from vprism.core.models.response import DataResponse, ProviderInfo, ResponseMetadata
from vprism.core.services.symbol_normalization import NormalizedSymbol


class RecordingDataService:
    def __init__(self) -> None:
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
        return _empty_response()


class NormalizerAllResolved:
    async def normalize(self, symbols: list[str], market: MarketType | None = None, **_: object) -> list[NormalizedSymbol]:
        resolved: list[NormalizedSymbol] = []
        for symbol in symbols:
            resolved.append(
                NormalizedSymbol(
                    raw=symbol,
                    c_symbol=symbol,
                    market=market or MarketType.CN,
                    confidence=1.0,
                    rule="stub",
                    unresolved=False,
                )
            )
        return resolved


def _empty_response() -> DataResponse:
    metadata = ResponseMetadata(total_records=0, query_time_ms=0.0, data_source="stub", cache_hit=False)
    provider = ProviderInfo(name="stub-provider")
    return DataResponse(data=[], metadata=metadata, source=provider)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_symbols_from_file_supplies_symbols(tmp_path: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    file_path = tmp_path / "symbols.txt"
    file_path.write_text("000001\n000002\n\n000001\n", encoding="utf-8")

    service = RecordingDataService()
    normalizer = NormalizerAllResolved()
    monkeypatch.setattr(data_module, "get_data_service", lambda: service)
    monkeypatch.setattr(data_module, "get_symbol_normalizer", lambda: normalizer)

    app = create_app()
    result = runner.invoke(app, ["data", "fetch", "--symbols-from", str(file_path)])

    assert result.exit_code == 0, result.output
    assert service.calls[0]["symbols"] == ["000001", "000002"]


def test_symbols_from_file_missing(tmp_path: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    missing = tmp_path / "missing.txt"

    service = RecordingDataService()
    normalizer = NormalizerAllResolved()
    monkeypatch.setattr(data_module, "get_data_service", lambda: service)
    monkeypatch.setattr(data_module, "get_symbol_normalizer", lambda: normalizer)

    app = create_app()
    result = runner.invoke(app, ["data", "fetch", "--symbols-from", str(missing)])

    assert result.exit_code == 10
    assert "SYMBOL_FILE_ERROR" in result.output
    assert service.calls == []
