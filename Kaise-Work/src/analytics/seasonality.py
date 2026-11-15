"""Seasonality and calendar analysis (M3) — descriptive aggregates.

Readings and fill levels by month, meteorological season and weekday, plus a
holiday vs non-holiday comparison. The holiday calendar (BW public holidays)
is EXTERNAL CALENDAR INPUT (src.analytics.holidays), not dataset-derived.
School vacations are NOT modelled (dates unverified — open question in
docs/eda_report.md); only public holidays are analysed.

All outputs are descriptive: reading counts measure observations in the source
file, whose semantics are unresolved (docs/data_profile.md §13.1) — no causal
claim is attached to any ratio below.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from src.analytics.holidays import GermanHoliday, bw_holidays_in_range
from src.data.schema import ReadingRecord

WEEKDAY_NAMES: tuple[str, ...] = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


@dataclass(frozen=True)
class MonthStats:
    """Per calendar month; month is ISO ``YYYY-MM``."""

    month: str
    n_readings: int
    n_numeric: int
    n_overfull: int
    mean_fill_pct: float | None  # numeric readings only; percent
    overfull_share: float  # fraction of all readings in the month
    n_bw_holidays: int  # EXTERNAL CALENDAR INPUT: BW holidays in that month


@dataclass(frozen=True)
class SeasonStats:
    """Per meteorological season; winter spans Dec of one year to Feb of next."""

    season: str  # e.g. "winter 2025/26", "summer 2026"
    n_readings: int
    n_numeric: int
    mean_fill_pct: float | None
    overfull_share: float


@dataclass(frozen=True)
class WeekdayStats:
    """Per weekday; readings_per_day normalises by weekday occurrences in range."""

    weekday: str
    n_readings: int
    n_distinct_dates: int
    n_days_in_range: int
    readings_per_day: float


@dataclass(frozen=True)
class HolidayDayStats:
    """One BW holiday in range with its reading count (0 = no readings)."""

    date: date
    name: str
    weekday: str
    n_readings: int


@dataclass(frozen=True)
class HolidayComparison:
    """Holiday vs non-holiday daily reading rates (descriptive, no causal claim)."""

    n_holidays: int
    holidays: tuple[HolidayDayStats, ...]
    readings_on_holiday_days: int
    readings_per_day_on_holidays: float
    readings_per_day_on_non_holidays: float
    weekday_matched_ratio: float  # actual holiday readings / same-weekday expectation


@dataclass(frozen=True)
class SeasonalityReport:
    """All seasonality aggregates for one dataset span."""

    date_min: date
    date_max: date
    n_readings: int
    months: tuple[MonthStats, ...]
    seasons: tuple[SeasonStats, ...]
    weekdays: tuple[WeekdayStats, ...]
    holiday_comparison: HolidayComparison


def season_label(year: int, month: int) -> tuple[str, tuple[int, int]]:
    """Meteorological season label and its (start_year, start_month) sort key."""
    if month == 12:
        return f"winter {year}/{str(year + 1)[-2:]}", (year, 12)
    if month in (1, 2):
        return f"winter {year - 1}/{str(year)[-2:]}", (year - 1, 12)
    if month in (3, 4, 5):
        return f"spring {year}", (year, 3)
    if month in (6, 7, 8):
        return f"summer {year}", (year, 6)
    return f"autumn {year}", (year, 9)


def weekday_name(day: date) -> str:
    return WEEKDAY_NAMES[day.weekday()]


def count_weekday_occurrences(start: date, end: date, weekday: int) -> int:
    """Occurrences of one ISO weekday (Mon=0..Sun=6) in [start, end] inclusive."""
    if start > end:
        return 0
    total_days = (end - start).days + 1
    full_weeks, remainder = divmod(total_days, 7)
    extra_occurrence = (weekday - start.weekday()) % 7 < remainder
    return int(full_weeks) + (1 if extra_occurrence else 0)


def compute_seasonality(
    readings: list[ReadingRecord],
    holidays: Iterable[GermanHoliday] | None = None,
) -> SeasonalityReport:
    """Aggregate readings by month/season/weekday and compare holiday days.

    ``holidays`` defaults to BW public holidays (EXTERNAL CALENDAR INPUT) in
    the dataset span; pass an explicit iterable to inject another calendar.
    """
    if not readings:
        raise ValueError("compute_seasonality requires at least one reading")
    dates = [r.date for r in readings]
    date_min, date_max = min(dates), max(dates)
    n_readings = len(readings)
    if holidays is None:
        holidays = bw_holidays_in_range(date_min, date_max)
    holiday_list = sorted(holidays, key=lambda h: h.date)
    holiday_dates = {h.date for h in holiday_list}

    months = _month_stats(readings, holiday_list)
    seasons = _season_stats(readings)
    weekdays = _weekday_stats(readings, date_min, date_max)
    comparison = _holiday_comparison(
        holiday_list, holiday_dates, weekdays, readings, date_min, date_max
    )
    return SeasonalityReport(
        date_min=date_min,
        date_max=date_max,
        n_readings=n_readings,
        months=months,
        seasons=seasons,
        weekdays=weekdays,
        holiday_comparison=comparison,
    )


def _mean_fill(rows: list[ReadingRecord]) -> float | None:
    fills = [r.fill_level_pct for r in rows if r.fill_level_pct is not None]
    return float(statistics.mean(fills)) if fills else None


def _month_stats(
    readings: list[ReadingRecord], holidays: list[GermanHoliday]
) -> tuple[MonthStats, ...]:
    by_month: dict[str, list[ReadingRecord]] = {}
    for r in readings:
        by_month.setdefault(r.date.strftime("%Y-%m"), []).append(r)
    stats: list[MonthStats] = []
    for month in sorted(by_month):
        year, m = int(month[:4]), int(month[5:7])
        rows = by_month[month]
        n_overfull = sum(1 for r in rows if r.is_overfull)
        stats.append(
            MonthStats(
                month=month,
                n_readings=len(rows),
                n_numeric=len(rows) - n_overfull,
                n_overfull=n_overfull,
                mean_fill_pct=_mean_fill(rows),
                overfull_share=n_overfull / len(rows),
                n_bw_holidays=sum(1 for h in holidays if h.date.year == year and h.date.month == m),
            )
        )
    return tuple(stats)


def _season_stats(readings: list[ReadingRecord]) -> tuple[SeasonStats, ...]:
    by_season: dict[str, tuple[tuple[int, int], list[ReadingRecord]]] = {}
    for r in readings:
        label, key = season_label(r.date.year, r.date.month)
        if label not in by_season:
            by_season[label] = (key, [])
        by_season[label][1].append(r)
    ordered = sorted(by_season.items(), key=lambda item: item[1][0])
    stats: list[SeasonStats] = []
    for label, (_, rows) in ordered:
        n_overfull = sum(1 for r in rows if r.is_overfull)
        stats.append(
            SeasonStats(
                season=label,
                n_readings=len(rows),
                n_numeric=len(rows) - n_overfull,
                mean_fill_pct=_mean_fill(rows),
                overfull_share=n_overfull / len(rows),
            )
        )
    return tuple(stats)


def _weekday_stats(
    readings: list[ReadingRecord], date_min: date, date_max: date
) -> tuple[WeekdayStats, ...]:
    by_weekday: dict[int, set[date]] = {w: set() for w in range(7)}
    counts = [0] * 7
    for r in readings:
        by_weekday[r.date.weekday()].add(r.date)
        counts[r.date.weekday()] += 1
    stats: list[WeekdayStats] = []
    for w in range(7):
        n_days = count_weekday_occurrences(date_min, date_max, w)
        stats.append(
            WeekdayStats(
                weekday=WEEKDAY_NAMES[w],
                n_readings=counts[w],
                n_distinct_dates=len(by_weekday[w]),
                n_days_in_range=n_days,
                readings_per_day=counts[w] / n_days,
            )
        )
    return tuple(stats)


def _holiday_comparison(
    holidays: list[GermanHoliday],
    holiday_dates: set[date],
    weekdays: tuple[WeekdayStats, ...],
    readings: list[ReadingRecord],
    date_min: date,
    date_max: date,
) -> HolidayComparison:
    readings_per_date: dict[date, int] = {}
    for r in readings:
        readings_per_date[r.date] = readings_per_date.get(r.date, 0) + 1
    holiday_days = tuple(
        HolidayDayStats(
            date=h.date,
            name=h.name,
            weekday=weekday_name(h.date),
            n_readings=readings_per_date.get(h.date, 0),
        )
        for h in holidays
    )
    readings_on_holidays = sum(d.n_readings for d in holiday_days)
    total_days = (date_max - date_min).days + 1
    n_non_holiday_days = total_days - len(holidays)
    readings_on_non_holidays = sum(
        n for d, n in readings_per_date.items() if d not in holiday_dates
    )
    rate_on = readings_on_holidays / len(holidays)
    rate_off = readings_on_non_holidays / n_non_holiday_days

    # Weekday-matched expectation: what holiday days would carry if they behaved
    # like non-holiday days of the same weekday (descriptive benchmark only).
    n_holiday_days_per_weekday = [0] * 7
    for d in holiday_days:
        n_holiday_days_per_weekday[WEEKDAY_NAMES.index(d.weekday)] += 1
    expected = 0.0
    for w, weekday_stat in enumerate(weekdays):
        n_non_holiday_w = weekday_stat.n_days_in_range - n_holiday_days_per_weekday[w]
        readings_non_w = weekday_stat.n_readings - _readings_of_weekday_on_holidays(holiday_days, w)
        if n_non_holiday_w > 0:
            expected += (readings_non_w / n_non_holiday_w) * n_holiday_days_per_weekday[w]
    ratio = readings_on_holidays / expected if expected > 0 else 0.0
    return HolidayComparison(
        n_holidays=len(holidays),
        holidays=holiday_days,
        readings_on_holiday_days=readings_on_holidays,
        readings_per_day_on_holidays=rate_on,
        readings_per_day_on_non_holidays=rate_off,
        weekday_matched_ratio=ratio,
    )


def _readings_of_weekday_on_holidays(holiday_days: tuple[HolidayDayStats, ...], w: int) -> int:
    return sum(d.n_readings for d in holiday_days if WEEKDAY_NAMES.index(d.weekday) == w)
