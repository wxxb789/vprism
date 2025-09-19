"""vprism trading calendar provider utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, MutableMapping

vprism_default_weekend = frozenset({5, 6})


def vprism_normalize_market(vprism_market: str) -> str:
    """Normalize market identifiers for vprism calendar lookups."""

    return vprism_market.lower()


@dataclass(frozen=True)
class VPrismTradingCalendar:
    """Represents a vprism trading calendar with optional aliases."""

    vprism_market: str
    vprism_weekend_days: frozenset[int] = vprism_default_weekend
    vprism_holidays: frozenset[date] = frozenset()
    vprism_aliases: frozenset[str] = frozenset()

    def vprism_trading_days(self, vprism_start: date, vprism_end: date) -> list[date]:
        """Return trading days between the provided bounds inclusive for vprism."""

        if vprism_end < vprism_start:
            raise ValueError("vprism_end must be on or after vprism_start")

        vprism_current = vprism_start
        vprism_days: list[date] = []
        while vprism_current <= vprism_end:
            vprism_weekday = vprism_current.weekday()
            if vprism_weekday not in self.vprism_weekend_days and vprism_current not in self.vprism_holidays:
                vprism_days.append(vprism_current)
            vprism_current += timedelta(days=1)
        return vprism_days


def vprism_builtin_calendars() -> Mapping[str, VPrismTradingCalendar]:
    """Construct built-in vprism trading calendars."""

    vprism_cn_calendar = VPrismTradingCalendar(
        vprism_market="cn",
        vprism_aliases=frozenset({"cn", "sh", "sz"}),
    )
    vprism_us_calendar = VPrismTradingCalendar(
        vprism_market="us",
        vprism_aliases=frozenset({"us", "nyse", "nasdaq"}),
        vprism_holidays=frozenset({date(2024, 1, 1)}),
    )
    vprism_hk_calendar = VPrismTradingCalendar(
        vprism_market="hk",
        vprism_aliases=frozenset({"hk", "sehk"}),
    )
    return {
        vprism_cn_calendar.vprism_market: vprism_cn_calendar,
        vprism_us_calendar.vprism_market: vprism_us_calendar,
        vprism_hk_calendar.vprism_market: vprism_hk_calendar,
    }


class VPrismTradingCalendarProvider:
    """Provides vprism trading calendars keyed by market identifiers."""

    def __init__(
        self,
        vprism_market_calendars: Mapping[str, VPrismTradingCalendar] | None = None,
        vprism_default_calendar: VPrismTradingCalendar | None = None,
    ) -> None:
        vprism_source = vprism_market_calendars or vprism_builtin_calendars()
        self._vprism_calendars: MutableMapping[str, VPrismTradingCalendar] = {}
        self._vprism_alias_map: MutableMapping[str, VPrismTradingCalendar] = {}
        for vprism_key, vprism_calendar in vprism_source.items():
            self._vprism_calendars[vprism_normalize_market(vprism_key)] = vprism_calendar
            for vprism_alias in vprism_calendar.vprism_aliases:
                self._vprism_alias_map[vprism_normalize_market(vprism_alias)] = vprism_calendar

        self._vprism_default_calendar = vprism_default_calendar or VPrismTradingCalendar(
            vprism_market="default",
        )

    def vprism_get_calendar(self, vprism_market: str) -> VPrismTradingCalendar:
        """Return the matching vprism calendar or fallback to default."""

        vprism_key = vprism_normalize_market(vprism_market)
        if vprism_key in self._vprism_calendars:
            return self._vprism_calendars[vprism_key]
        if vprism_key in self._vprism_alias_map:
            return self._vprism_alias_map[vprism_key]
        return self._vprism_default_calendar

    def vprism_get_trading_days(self, vprism_market: str, vprism_start: date, vprism_end: date) -> list[date]:
        """Helper retrieving trading days for the requested vprism market."""

        vprism_calendar = self.vprism_get_calendar(vprism_market)
        return vprism_calendar.vprism_trading_days(vprism_start, vprism_end)


__all__ = [
    "VPrismTradingCalendar",
    "VPrismTradingCalendarProvider",
    "vprism_builtin_calendars",
    "vprism_default_weekend",
    "vprism_normalize_market",
]
