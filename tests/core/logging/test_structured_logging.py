"""Tests for structured logging with trace propagation."""

from __future__ import annotations

import io
import json

from vprism.core.logging import LogConfig, StructuredLogger


def _read_records(stream: io.StringIO) -> list[dict[str, object]]:
    stream.seek(0)
    lines = [line for line in stream.getvalue().splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def test_structured_log_contains_trace_and_context() -> None:
    buffer = io.StringIO()
    config = LogConfig(console_stream=buffer, console_output=True, file_output=False)
    logger = StructuredLogger(config)

    with logger.context(trace_id="trace-123", provider="alpha-feed", error_code="DATA_QUALITY", request_id="req-42"):
        logger.logger.info("normalization complete", symbol="AAPL")

    records = _read_records(buffer)
    assert len(records) == 1
    record = records[0]
    assert record["trace_id"] == "trace-123"
    assert record["provider"] == "alpha-feed"
    assert record["error_code"] == "DATA_QUALITY"
    assert record["context"]["request_id"] == "req-42"
    assert record["context"]["symbol"] == "AAPL"


def test_trace_id_propagates_within_context() -> None:
    buffer = io.StringIO()
    logger = StructuredLogger(LogConfig(console_stream=buffer, console_output=True, file_output=False))

    with logger.context() as trace_id:
        logger.logger.info("first event")
        logger.logger.info("second event")

    logger.logger.info("outside context")

    records = _read_records(buffer)
    assert len(records) == 3
    assert records[0]["trace_id"] == records[1]["trace_id"]
    assert records[0]["trace_id"] == trace_id
    assert records[2]["trace_id"] != records[0]["trace_id"]


def test_trace_id_generated_when_missing() -> None:
    buffer = io.StringIO()
    logger = StructuredLogger(LogConfig(console_stream=buffer, console_output=True, file_output=False))

    logger.logger.info("single message")

    records = _read_records(buffer)
    assert len(records) == 1
    trace_id = records[0]["trace_id"]
    assert isinstance(trace_id, str)
    assert len(trace_id) == 32
    assert all(character in "0123456789abcdef" for character in trace_id)
