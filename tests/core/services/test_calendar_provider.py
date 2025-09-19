from __future__ import annotations

from datetime import date

from vprism.core.services.calendars import VPrismTradingCalendarProvider


def test_calendar_known_market_trading_days() -> None:
    vprism_provider = VPrismTradingCalendarProvider()

    vprism_days = vprism_provider.vprism_get_trading_days(
        "cn",
        date(2024, 1, 1),
        date(2024, 1, 7),
    )

    assert vprism_days == [
        date(2024, 1, 1),
        date(2024, 1, 2),
        date(2024, 1, 3),
        date(2024, 1, 4),
        date(2024, 1, 5),
    ]


def test_calendar_alias_lookup_returns_expected_calendar() -> None:
    vprism_provider = VPrismTradingCalendarProvider()

    vprism_calendar = vprism_provider.vprism_get_calendar("SZ")

    assert vprism_calendar.vprism_market == "cn"


def test_calendar_fallback_uses_default_weekmask() -> None:
    vprism_provider = VPrismTradingCalendarProvider()

    vprism_calendar = vprism_provider.vprism_get_calendar("unknown-market")
    vprism_days = vprism_calendar.vprism_trading_days(
        date(2024, 1, 6),
        date(2024, 1, 7),
    )

    assert vprism_days == []


def test_calendar_holiday_excluded_for_us_market() -> None:
    vprism_provider = VPrismTradingCalendarProvider()

    vprism_days = vprism_provider.vprism_get_trading_days(
        "us",
        date(2023, 12, 29),
        date(2024, 1, 2),
    )

    assert date(2024, 1, 1) not in vprism_days
    assert date(2024, 1, 2) in vprism_days
