from __future__ import annotations

import pytest

from vprism.core.services.shadow import ShadowPromoteGuard
from vprism.core.services.shadow_diff import ShadowDiffStatus


def test_guard_requires_consecutive_passes() -> None:
    guard = ShadowPromoteGuard(required_passes=3)
    guard.observe(ShadowDiffStatus.PASS)
    guard.observe(ShadowDiffStatus.PASS)
    assert guard.ready is False
    guard.observe(ShadowDiffStatus.PASS)
    assert guard.ready is True
    assert guard.consecutive_passes == 3


def test_guard_resets_on_failure() -> None:
    guard = ShadowPromoteGuard(required_passes=2)
    guard.observe(ShadowDiffStatus.PASS)
    guard.observe(ShadowDiffStatus.FAIL)
    assert guard.ready is False
    assert guard.consecutive_passes == 0


def test_guard_configuration_override() -> None:
    guard = ShadowPromoteGuard(required_passes=2)
    guard.observe(ShadowDiffStatus.PASS)
    guard.configure(required_passes=1)
    assert guard.ready is False
    guard.observe(ShadowDiffStatus.PASS)
    assert guard.ready is True

    with pytest.raises(ValueError):
        guard.configure(0)
