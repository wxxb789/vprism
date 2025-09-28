from __future__ import annotations

import pytest
from typer.testing import CliRunner

from vprism.cli import symbol as symbol_module
from vprism.cli.main import create_app
from vprism.core.exceptions.base import UnresolvedSymbolError
from vprism.core.models.market import AssetType, MarketType
from vprism.core.models.symbols import CanonicalSymbol


class StubSymbolService:
    def __init__(self, canonical: CanonicalSymbol | None = None, error: Exception | None = None) -> None:
        self.canonical = canonical
        self.error = error
        self.calls: list[tuple[str, MarketType, AssetType]] = []

    def normalize(self, raw_symbol: str, market: MarketType, asset_type: AssetType) -> CanonicalSymbol:
        self.calls.append((raw_symbol, market, asset_type))
        if self.error is not None:
            raise self.error
        assert self.canonical is not None
        return self.canonical


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_symbol_resolve_table_output(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    canonical = CanonicalSymbol(
        raw_symbol="000001",
        canonical="000001",
        market=MarketType.CN,
        asset_type=AssetType.STOCK,
        rule_id="cn-rule",
    )
    service = StubSymbolService(canonical=canonical)
    monkeypatch.setattr(symbol_module, "get_symbol_service", lambda: service)

    app = create_app()
    result = runner.invoke(app, ["symbol", "resolve", "000001"])

    assert result.exit_code == 0, result.output
    assert "000001" in result.output
    assert "rule" in result.output
    assert service.calls == [("000001", MarketType.CN, AssetType.STOCK)]


def test_symbol_resolve_jsonl_output(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    canonical = CanonicalSymbol(
        raw_symbol="600519",
        canonical="600519",
        market=MarketType.CN,
        asset_type=AssetType.STOCK,
        rule_id="cn-rule",
    )
    service = StubSymbolService(canonical=canonical)
    monkeypatch.setattr(symbol_module, "get_symbol_service", lambda: service)

    app = create_app()
    result = runner.invoke(app, ["--format", "jsonl", "symbol", "resolve", "600519"])

    assert result.exit_code == 0, result.output
    assert result.output.strip().startswith("{\"raw_symbol\": \"600519\"")
    assert "\"rule_id\": \"cn-rule\"" in result.output


def test_symbol_resolve_unresolved_symbol(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    error = UnresolvedSymbolError(
        "Cannot resolve symbol",
        raw_symbol="BAD",
        market="cn",
        asset_type="stock",
        details={"symbols": ["BAD"]},
    )
    service = StubSymbolService(error=error)
    monkeypatch.setattr(symbol_module, "get_symbol_service", lambda: service)

    app = create_app()
    result = runner.invoke(app, ["symbol", "resolve", "BAD"])

    assert result.exit_code == 10
    assert "SYMBOL_UNRESOLVED" in result.output
    assert "BAD" in result.output
