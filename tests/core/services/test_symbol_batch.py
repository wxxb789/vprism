import pytest

from vprism.core.exceptions.base import UnresolvedSymbolError
from vprism.core.models.market import AssetType, MarketType
from vprism.core.services.symbols import SymbolService


@pytest.mark.parametrize(
    "raw_symbols",
    [
        ["000001.SZ", "600519.SH", "@@INVALID@@"],
        [" 000001.SZ ", "600519.SH", " @@INVALID@@ "],
    ],
)
def test_normalize_batch_mixed_results(raw_symbols: list[str]) -> None:
    service = SymbolService()

    result = service.normalize_batch(raw_symbols, MarketType.CN, AssetType.STOCK)

    assert len(result.items) == len(raw_symbols)
    assert [item.status for item in result.items] == ["resolved", "resolved", "unresolved"]

    resolved_canonicals = [item.canonical for item in result.items if item.status == "resolved"]
    assert len(resolved_canonicals) == 2
    assert all(canonical is not None for canonical in resolved_canonicals)
    canonical_values = {canonical.canonical for canonical in resolved_canonicals if canonical}
    assert canonical_values == {"CN:STOCK:SZ000001", "CN:STOCK:SH600519"}

    assert len(result.successes) == 2
    assert {symbol.raw_symbol for symbol in result.successes} == {"000001.SZ", "600519.SH"}

    assert len(result.failures) == 1
    failure = result.failures[0]
    assert isinstance(failure, UnresolvedSymbolError)
    assert failure.details["raw_symbol"] == "@@INVALID@@"

    unresolved_items = [item for item in result.items if item.status == "unresolved"]
    assert len(unresolved_items) == 1
    assert unresolved_items[0].error is failure


def test_normalize_batch_updates_metrics_and_cache() -> None:
    service = SymbolService()

    first_batch = service.normalize_batch(
        ["000001.SZ", "000001.SZ", "@@INVALID@@"],
        MarketType.CN,
        AssetType.STOCK,
    )

    metrics = service.get_metrics()
    assert metrics["total_requests"] == 3
    assert metrics["cache_misses"] == 2
    assert metrics["cache_hits"] == 1
    assert metrics["unresolved_count"] == 1

    assert len(first_batch.successes) == 2
    assert len(first_batch.failures) == 1

    second_batch = service.normalize_batch(["000001.SZ"], MarketType.CN, AssetType.STOCK)
    assert len(second_batch.failures) == 0
    assert len(second_batch.successes) == 1

    metrics_after_second = service.get_metrics()
    assert metrics_after_second["total_requests"] == 4
    assert metrics_after_second["cache_hits"] == 2
    assert metrics_after_second["cache_misses"] == 2
    assert metrics_after_second["unresolved_count"] == 1
