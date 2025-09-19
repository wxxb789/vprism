"""Threshold utilities for vprism quality metrics."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import TYPE_CHECKING, SupportsFloat, TypedDict

from vprism.core.data.schema import VPrismQualityMetricStatus

if TYPE_CHECKING:
    from collections.abc import Mapping


class VPrismThresholdDirection(str, Enum):
    """Enumerates vprism threshold comparison directions."""

    ABOVE = "above"
    BELOW = "below"


class VPrismThresholdOverride(TypedDict, total=False):
    """Typed mapping describing override payloads for thresholds."""

    warn: SupportsFloat
    fail: SupportsFloat
    direction: VPrismThresholdDirection | str


@dataclass(frozen=True)
class VPrismMetricThresholds:
    """Represents warn/fail thresholds for a vprism metric."""

    warn: float
    fail: float
    direction: VPrismThresholdDirection = VPrismThresholdDirection.ABOVE

    def vprism_classify(self, vprism_value: float) -> VPrismQualityMetricStatus:
        """Classify a value according to the configured vprism thresholds."""

        if self.direction is VPrismThresholdDirection.ABOVE:
            if vprism_value >= self.fail:
                return VPrismQualityMetricStatus.FAIL
            if vprism_value >= self.warn:
                return VPrismQualityMetricStatus.WARN
            return VPrismQualityMetricStatus.OK

        if vprism_value <= self.fail:
            return VPrismQualityMetricStatus.FAIL
        if vprism_value <= self.warn:
            return VPrismQualityMetricStatus.WARN
        return VPrismQualityMetricStatus.OK


def vprism_normalize_direction(
    vprism_direction: VPrismThresholdDirection | str | None,
) -> VPrismThresholdDirection:
    """Convert override direction payloads into enum members."""

    if vprism_direction is None:
        return VPrismThresholdDirection.ABOVE
    if isinstance(vprism_direction, VPrismThresholdDirection):
        return vprism_direction
    return VPrismThresholdDirection(vprism_direction)


def vprism_classify_metric(vprism_value: float, thresholds: VPrismMetricThresholds) -> VPrismQualityMetricStatus:
    """Convenience wrapper returning the vprism metric classification."""

    return thresholds.vprism_classify(vprism_value)


def vprism_merge_threshold_overrides(
    vprism_defaults: Mapping[str, VPrismMetricThresholds],
    vprism_overrides: Mapping[str, VPrismThresholdOverride] | None = None,
) -> dict[str, VPrismMetricThresholds]:
    """Merge overrides into default vprism metric thresholds."""

    vprism_merged: dict[str, VPrismMetricThresholds] = dict(vprism_defaults)
    if not vprism_overrides:
        return dict(vprism_merged)

    for vprism_metric_name, vprism_override in vprism_overrides.items():
        vprism_base = vprism_merged.get(vprism_metric_name)
        if vprism_base is None:
            vprism_warn_override = vprism_override.get("warn")
            vprism_fail_override = vprism_override.get("fail")
            if vprism_warn_override is None or vprism_fail_override is None:
                raise ValueError(f"override for {vprism_metric_name} must define warn and fail values")
            vprism_direction = vprism_normalize_direction(vprism_override.get("direction"))
            vprism_merged[vprism_metric_name] = VPrismMetricThresholds(
                warn=float(vprism_warn_override),
                fail=float(vprism_fail_override),
                direction=vprism_direction,
            )
            continue

        vprism_new_thresholds = vprism_base
        vprism_warn_override = vprism_override.get("warn")
        if vprism_warn_override is not None:
            vprism_new_thresholds = replace(vprism_new_thresholds, warn=float(vprism_warn_override))
        vprism_fail_override = vprism_override.get("fail")
        if vprism_fail_override is not None:
            vprism_new_thresholds = replace(vprism_new_thresholds, fail=float(vprism_fail_override))
        if "direction" in vprism_override:
            vprism_new_thresholds = replace(
                vprism_new_thresholds,
                direction=vprism_normalize_direction(vprism_override["direction"]),
            )
        vprism_merged[vprism_metric_name] = vprism_new_thresholds

    return dict(vprism_merged)


__all__ = [
    "VPrismMetricThresholds",
    "VPrismThresholdDirection",
    "vprism_classify_metric",
    "vprism_merge_threshold_overrides",
]
