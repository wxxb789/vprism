"""Pytest configuration for vprism test suite."""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register command-line options for controlling integration tests."""

    parser.addoption(
        "--vprism-run-integration",
        action="store_true",
        default=False,
        help="Run vprism integration tests that require external services.",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register the integration marker for vprism tests."""

    config.addinivalue_line(
        "markers",
        "integration: marks vprism tests requiring network or external services",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip integration tests unless explicitly requested."""

    if config.getoption("--vprism-run-integration"):
        return

    vprism_skip_integration = pytest.mark.skip(
        reason="integration tests require --vprism-run-integration",
    )
    for vprism_item in items:
        if "integration" in vprism_item.keywords:
            vprism_item.add_marker(vprism_skip_integration)
