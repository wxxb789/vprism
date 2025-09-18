from __future__ import annotations

import json
from textwrap import dedent
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from vprism.core.exceptions.base import DataValidationError
from vprism.core.models.market import AssetType, MarketType
from vprism.core.services.symbol_rule_loader import (
    load_symbol_rules,
    load_symbol_rules_from_mapping,
)
from vprism.core.services.symbols import SymbolService


def test_load_symbol_rules_from_yaml_file(tmp_path: Path) -> None:
    config_text = dedent(
        r"""
        rules:
          - id: cn_stock_suffix
            priority: 10
            pattern: '^(?P<code>\d{6})\.(?P<suffix>[A-Za-z]{2})$'
            flags: ["IGNORECASE"]
            transform:
              type: map_template
              group: suffix
              mapping:
                SS: SH
                SH: SH
                SZ: SZ
              template: "{mapped}{code}"
            market_scope: ["CN"]
            asset_scope: ["stock"]
          - id: cn_stock_numeric
            priority: 20
            pattern: '^(?P<code>\d{6})$'
            transform:
              type: template
              template: "{code}"
            market_scope: ["CN"]
            asset_scope: ["stock"]
        """
    )
    config_path = tmp_path / "rules.yaml"
    config_path.write_text(config_text, encoding="utf-8")

    rules = load_symbol_rules(config_path)
    service = SymbolService(rules=rules)

    assert service.normalize("600000.SS", MarketType.CN, AssetType.STOCK).canonical == "CN:STOCK:SH600000"
    assert service.normalize("000001", MarketType.CN, AssetType.STOCK).canonical == "CN:STOCK:000001"


def test_load_symbol_rules_from_mapping_rejects_invalid_definition() -> None:
    config = {
        "rules": [
            {
                "priority": "high",  # invalid priority type
                "pattern": "^.+$",
                "transform": {"type": "template", "template": "{match}"},
            }
        ]
    }

    with pytest.raises(DataValidationError):
        load_symbol_rules_from_mapping(config)


def test_load_symbol_rules_from_file_rejects_unknown_suffix(tmp_path: Path) -> None:
    config = {"rules": []}
    path = tmp_path / "rules.toml"
    path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(DataValidationError):
        load_symbol_rules(path)
