from __future__ import annotations

import pytest

from vprism.core.data.schema import VPrismQualityMetricStatus
from vprism.core.services.quality.thresholds import (
    VPrismMetricThresholds,
    VPrismThresholdDirection,
    vprism_classify_metric,
    vprism_merge_threshold_overrides,
)


def test_classify_metric_above_direction_boundaries() -> None:
    vprism_thresholds = VPrismMetricThresholds(warn=0.1, fail=0.2)

    assert vprism_classify_metric(0.05, vprism_thresholds) == VPrismQualityMetricStatus.OK
    assert vprism_classify_metric(0.1, vprism_thresholds) == VPrismQualityMetricStatus.WARN
    assert vprism_classify_metric(0.25, vprism_thresholds) == VPrismQualityMetricStatus.FAIL


def test_classify_metric_below_direction_boundaries() -> None:
    vprism_thresholds = VPrismMetricThresholds(
        warn=0.9,
        fail=0.8,
        direction=VPrismThresholdDirection.BELOW,
    )

    assert vprism_classify_metric(0.95, vprism_thresholds) == VPrismQualityMetricStatus.OK
    assert vprism_classify_metric(0.9, vprism_thresholds) == VPrismQualityMetricStatus.WARN
    assert vprism_classify_metric(0.7, vprism_thresholds) == VPrismQualityMetricStatus.FAIL


def test_merge_threshold_overrides_updates_defaults() -> None:
    vprism_defaults = {
        "gap_ratio": VPrismMetricThresholds(warn=0.05, fail=0.1),
        "duplicate_count": VPrismMetricThresholds(warn=1, fail=3),
    }
    vprism_overrides = {
        "gap_ratio": {"warn": 0.1},
        "new_metric": {"warn": 2, "fail": 4, "direction": "below"},
    }

    vprism_merged = vprism_merge_threshold_overrides(vprism_defaults, vprism_overrides)

    assert pytest.approx(vprism_merged["gap_ratio"].warn) == 0.1
    assert vprism_merged["gap_ratio"].fail == 0.1
    assert vprism_merged["duplicate_count"].warn == 1
    assert vprism_merged["new_metric"].direction is VPrismThresholdDirection.BELOW
    assert vprism_merged["new_metric"].fail == 4


def test_merge_threshold_overrides_requires_values_for_new_metric() -> None:
    with pytest.raises(ValueError):
        vprism_merge_threshold_overrides({}, {"gap_ratio": {"warn": 0.1}})
