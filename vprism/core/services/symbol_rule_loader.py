from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from string import Formatter
from typing import Any

from vprism.core.exceptions.base import DataValidationError
from vprism.core.models.market import AssetType, MarketType
from vprism.core.models.symbols import RuleTransform, SymbolRule

_ALLOWED_FILE_SUFFIXES = {".yaml", ".yml", ".json"}


class _TemplateDict(dict[str, str]):
    """Dictionary used for formatting to ensure strict key access."""

    def __missing__(self, key: str) -> str:  # pragma: no cover - defensive
        raise KeyError(key)


def load_symbol_rules(path: str | Path) -> tuple[SymbolRule, ...]:
    """Load symbol normalization rules from a YAML or JSON file."""

    file_path = Path(path)
    if not file_path.exists():
        raise DataValidationError(
            "Symbol rule configuration file does not exist.",
            details={"path": str(file_path)},
        )

    suffix = file_path.suffix.lower()
    if suffix not in _ALLOWED_FILE_SUFFIXES:
        raise DataValidationError(
            "Unsupported symbol rule file type.",
            details={"path": str(file_path), "suffix": suffix},
        )

    content = file_path.read_text(encoding="utf-8")
    config: Any
    if suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError as exc:  # pragma: no cover - environment guard
            raise DataValidationError(
                "PyYAML is required to load YAML rule files.",
                details={"path": str(file_path)},
            ) from exc
        config = yaml.safe_load(content)
    else:
        config = json.loads(content)

    if config is None:
        raise DataValidationError(
            "Symbol rule configuration must not be empty.",
            details={"path": str(file_path)},
        )

    if not isinstance(config, Mapping):
        raise DataValidationError(
            "Symbol rule configuration must be a mapping at the top level.",
            details={"path": str(file_path)},
        )

    return load_symbol_rules_from_mapping(config)


def load_symbol_rules_from_mapping(config: Mapping[str, Any]) -> tuple[SymbolRule, ...]:
    """Convert a configuration mapping into :class:`SymbolRule` instances."""

    raw_rules = config.get("rules")
    if not isinstance(raw_rules, list):
        raise DataValidationError(
            "Symbol rule configuration requires a 'rules' list.",
            details={"provided_type": type(raw_rules).__name__},
        )

    rules: list[SymbolRule] = []
    seen_ids: set[str] = set()
    for index, raw_rule in enumerate(raw_rules):
        if not isinstance(raw_rule, Mapping):
            raise DataValidationError(
                "Each rule entry must be a mapping.",
                details={"index": index},
            )
        rule = _parse_rule(raw_rule, index)
        if rule.id in seen_ids:
            raise DataValidationError(
                "Duplicate rule identifiers are not allowed.",
                details={"rule_id": rule.id},
            )
        seen_ids.add(rule.id)
        rules.append(rule)

    return tuple(rules)


def _parse_rule(raw_rule: Mapping[str, Any], index: int) -> SymbolRule:
    rule_id = raw_rule.get("id")
    if not isinstance(rule_id, str) or not rule_id.strip():
        raise DataValidationError(
            "Symbol rule must define a non-empty string 'id'.",
            details={"index": index},
        )

    priority = raw_rule.get("priority")
    if not isinstance(priority, int):
        raise DataValidationError(
            "Symbol rule must define an integer 'priority'.",
            details={"rule_id": rule_id},
        )

    pattern_value = raw_rule.get("pattern")
    if not isinstance(pattern_value, str) or not pattern_value:
        raise DataValidationError(
            "Symbol rule must define a regex 'pattern'.",
            details={"rule_id": rule_id},
        )

    flags_value = raw_rule.get("flags", [])
    flags = _resolve_regex_flags(flags_value, rule_id)
    pattern = re.compile(pattern_value, flags)

    transform_spec = raw_rule.get("transform")
    transform = _parse_transform(transform_spec, pattern, rule_id)

    market_scope = _parse_market_scope(raw_rule.get("market_scope"), rule_id)
    asset_scope = _parse_asset_scope(raw_rule.get("asset_scope"), rule_id)

    prefix = raw_rule.get("prefix")
    if prefix is not None and not isinstance(prefix, str):
        raise DataValidationError(
            "Symbol rule 'prefix' must be a string when provided.",
            details={"rule_id": rule_id},
        )

    suffix = raw_rule.get("suffix")
    if suffix is not None and not isinstance(suffix, str):
        raise DataValidationError(
            "Symbol rule 'suffix' must be a string when provided.",
            details={"rule_id": rule_id},
        )

    return SymbolRule(
        id=rule_id,
        priority=priority,
        pattern=pattern,
        transform=transform,
        market_scope=market_scope,
        asset_scope=asset_scope,
        prefix=prefix,
        suffix=suffix,
    )


def _resolve_regex_flags(flags_value: Any, rule_id: str) -> int:
    if flags_value is None:
        return 0
    if not isinstance(flags_value, Iterable) or isinstance(flags_value, str | bytes):
        raise DataValidationError(
            "Regex flags must be provided as a list of strings.",
            details={"rule_id": rule_id},
        )

    resolved = 0
    for flag_name in flags_value:
        if not isinstance(flag_name, str):
            raise DataValidationError(
                "Regex flag names must be strings.",
                details={"rule_id": rule_id},
            )
        try:
            resolved |= getattr(re, flag_name)
        except AttributeError as exc:
            raise DataValidationError(
                "Unsupported regex flag specified for symbol rule.",
                details={"rule_id": rule_id, "flag": flag_name},
            ) from exc
    return resolved


def _parse_transform(transform_spec: Any, pattern: re.Pattern[str], rule_id: str) -> RuleTransform:
    if not isinstance(transform_spec, Mapping):
        raise DataValidationError(
            "Symbol rule requires a 'transform' mapping.",
            details={"rule_id": rule_id},
        )

    transform_type = transform_spec.get("type")
    if not isinstance(transform_type, str):
        raise DataValidationError(
            "Transform definitions must include a string 'type'.",
            details={"rule_id": rule_id},
        )

    if transform_type == "template":
        return _build_template_transform(transform_spec, pattern, rule_id)
    if transform_type == "map_template":
        return _build_map_template_transform(transform_spec, pattern, rule_id)

    raise DataValidationError(
        "Unsupported transform type for symbol rule.",
        details={"rule_id": rule_id, "type": transform_type},
    )


def _build_template_transform(transform_spec: Mapping[str, Any], pattern: re.Pattern[str], rule_id: str) -> RuleTransform:
    template = transform_spec.get("template")
    if not isinstance(template, str) or not template:
        raise DataValidationError(
            "Template transform requires a non-empty 'template' string.",
            details={"rule_id": rule_id},
        )

    uppercase = bool(transform_spec.get("uppercase", False))
    allowed_fields = set(pattern.groupindex.keys()) | {"match"}
    requested_fields = {field for _, field, _, _ in Formatter().parse(template) if field not in (None, "")}
    missing = requested_fields - allowed_fields
    if missing:
        raise DataValidationError(
            "Template references unknown regex groups.",
            details={"rule_id": rule_id, "unknown_fields": sorted(missing)},
        )

    def _transform(raw_symbol: str, match: re.Match[str]) -> str:
        context = {key: (value or "") for key, value in match.groupdict().items()}
        context["match"] = match.group(0)
        result = template.format_map(_TemplateDict(context))
        return result.upper() if uppercase else result

    return _transform


def _build_map_template_transform(transform_spec: Mapping[str, Any], pattern: re.Pattern[str], rule_id: str) -> RuleTransform:
    template = transform_spec.get("template")
    if not isinstance(template, str) or not template:
        raise DataValidationError(
            "map_template transform requires a 'template' string.",
            details={"rule_id": rule_id},
        )

    group_name = transform_spec.get("group")
    if not isinstance(group_name, str) or group_name not in pattern.groupindex:
        raise DataValidationError(
            "map_template transform requires a valid regex group name.",
            details={"rule_id": rule_id, "group": group_name},
        )

    mapping_spec = transform_spec.get("mapping")
    if not isinstance(mapping_spec, Mapping) or not mapping_spec:
        raise DataValidationError(
            "map_template transform requires a non-empty 'mapping' dict.",
            details={"rule_id": rule_id},
        )

    case_insensitive = bool(transform_spec.get("case_insensitive", True))
    normalized_mapping: dict[str, str] = {}
    for raw_key, mapped_value in mapping_spec.items():
        if not isinstance(raw_key, str) or not isinstance(mapped_value, str):
            raise DataValidationError(
                "Mapping keys and values must be strings.",
                details={"rule_id": rule_id},
            )
        key = raw_key.upper() if case_insensitive else raw_key
        normalized_mapping[key] = mapped_value

    default_value = transform_spec.get("default")
    if default_value is not None and not isinstance(default_value, str):
        raise DataValidationError(
            "map_template default must be a string or omitted.",
            details={"rule_id": rule_id},
        )

    uppercase = bool(transform_spec.get("uppercase", False))
    allowed_fields = set(pattern.groupindex.keys()) | {"match", "mapped"}
    requested_fields = {field for _, field, _, _ in Formatter().parse(template) if field not in (None, "")}
    missing = requested_fields - allowed_fields
    if missing:
        raise DataValidationError(
            "map_template references unknown template fields.",
            details={"rule_id": rule_id, "unknown_fields": sorted(missing)},
        )

    def _lookup(original: str) -> str:
        lookup_key = original.upper() if case_insensitive else original
        mapped = normalized_mapping.get(lookup_key)
        if mapped is not None:
            return mapped
        if default_value is not None:
            return default_value.replace("{value}", original)
        return original

    def _transform(raw_symbol: str, match: re.Match[str]) -> str:
        context = {key: (value or "") for key, value in match.groupdict().items()}
        context["match"] = match.group(0)
        raw_group_value = match.group(group_name) or ""
        context["mapped"] = _lookup(raw_group_value)
        result = template.format_map(_TemplateDict(context))
        return result.upper() if uppercase else result

    return _transform


def _parse_market_scope(scope_value: Any, rule_id: str) -> frozenset[MarketType]:
    if scope_value is None:
        return frozenset()
    if not isinstance(scope_value, Iterable) or isinstance(scope_value, str | bytes):
        raise DataValidationError(
            "market_scope must be a list of market identifiers.",
            details={"rule_id": rule_id},
        )

    markets: list[MarketType] = []
    for market_name in scope_value:
        if not isinstance(market_name, str):
            raise DataValidationError(
                "market_scope entries must be strings.",
                details={"rule_id": rule_id},
            )
        try:
            markets.append(MarketType(market_name.lower()))
        except ValueError as exc:
            raise DataValidationError(
                "Unknown market value provided in market_scope.",
                details={"rule_id": rule_id, "market": market_name},
            ) from exc
    return frozenset(markets)


def _parse_asset_scope(scope_value: Any, rule_id: str) -> frozenset[AssetType]:
    if scope_value is None:
        return frozenset()
    if not isinstance(scope_value, Iterable) or isinstance(scope_value, str | bytes):
        raise DataValidationError(
            "asset_scope must be a list of asset identifiers.",
            details={"rule_id": rule_id},
        )

    assets: list[AssetType] = []
    for asset_name in scope_value:
        if not isinstance(asset_name, str):
            raise DataValidationError(
                "asset_scope entries must be strings.",
                details={"rule_id": rule_id},
            )
        try:
            assets.append(AssetType(asset_name.lower()))
        except ValueError as exc:
            raise DataValidationError(
                "Unknown asset value provided in asset_scope.",
                details={"rule_id": rule_id, "asset": asset_name},
            ) from exc
    return frozenset(assets)


__all__ = ["load_symbol_rules", "load_symbol_rules_from_mapping"]
