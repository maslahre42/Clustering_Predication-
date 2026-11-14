"""Tests for src.analytics.seasonality — month/season/weekday/holiday aggregates.

Fixture: tests/fixtures/synthetic_seasonality.csv (SYNTHETIC, engineered so the
expected aggregates below are hand-computable). Holiday dates are EXTERNAL
CALENDAR INPUT (public BW calendar facts asserted in tests/analytics/
test_holidays.py), not dataset observations.
"""

from datetime import date
from pathlib import Path

import pytest

from src.analytics.holidays import bw_holidays_in_range
from src.analytics.seasonality import (
    compute_seasonality,
    count_weekday_occurrences,
    season_label,
    weekday_name,
)
from src.data.loader import load_glass_fill_csv

FIXTURES = Path("tests/fixtures")


def _load(name: str):
    result = load_glass_fill_csv(FIXTURES / name)
    assert not result.errors, f"fixture {name} must load cleanly: {result.errors}"
    return result.dataset.readings


@pytest.fixture()
def report():
    return compute_seasonality(_load("synthetic_seasonality.csv"))


class TestSeasonLabel:
    def test_winter_spans_years(self) -> None:
        assert season_label(2025, 12) == ("winter 2025/26", (2025, 12))
        assert season_label(2026, 1) == ("winter 2025/26", (2025, 12))

    def test_other_seasons(self) -> None:
        assert season_label(2026, 4) == ("spring 2026", (2026, 3))
        assert season_label(2026, 7) == ("summer 2026", (2026, 6))
        assert season_label(2025, 11) == ("autumn 2025", (2025, 9))


class TestWeekdayHelpers:
    def test_weekday_name(self) -> None:
        assert weekday_name(date(2025, 11, 3)) == "Mon"
        assert weekday_name(date(2025, 12, 25)) == "Thu"

    def test_count_weekday_occurrences_full_range(self) -> None:
        # 2025-11-03 (Mon) .. 2026-08-12 (Wed) = 283 days = 40 weeks + 3 days,
        # starting Monday -> Mon/Tue/Wed occur 41x, Thu..Sun 40x.
        start, end = date(2025, 11, 3), date(2026, 8, 12)
        assert count_weekday_occurrences(start, end, 0) == 41  # Mon
        assert count_weekday_occurrences(start, end, 3) == 40  # Thu
        assert count_weekday_occurrences(start, end, 6) == 40  # Sun

    def test_count_weekday_occurrences_single_day(self) -> None:
        assert count_weekday_occurrences(date(2026, 5, 14), date(2026, 5, 14), 3) == 1
        assert count_weekday_occurrences(date(2026, 5, 14), date(2026, 5, 14), 0) == 0

    def test_empty_range(self) -> None:
        assert count_weekday_occurrences(date(2026, 5, 14), date(2026, 5, 1), 0) == 0


class TestMonthlyStats:
    def test_monthly_counts(self, report) -> None:
        counts = {m.month: m.n_readings for m in report.months}
        assert counts == {
            "2025-11": 2,
            "2025-12": 6,
            "2026-01": 1,
            "2026-06": 2,
            "2026-08": 2,
        }

    def test_monthly_holiday_counts_are_external_calendar_input(self, report) -> None:
        counts = {m.month: m.n_bw_holidays for m in report.months}
        assert counts == {
            "2025-11": 0,  # Nov 1 outside dataset span (min = Nov 3)
            "2025-12": 2,  # Dec 25 + Dec 26
            "2026-01": 2,  # Jan 1 + Jan 6 (Epiphany BW)
            "2026-06": 1,  # Corpus Christi (BW)
            "2026-08": 0,
        }

    def test_monthly_fill_and_overfull(self, report) -> None:
        dec = next(m for m in report.months if m.month == "2025-12")
        assert dec.n_numeric == 5  # Dec-01 + Dec-25 x2 + Dec-26 x2
        assert dec.n_overfull == 1
        assert dec.mean_fill_pct == pytest.approx((40 + 90 + 100 + 80 + 100) / 5)
        assert dec.overfull_share == pytest.approx(1 / 6)


class TestSeasonStats:
    def test_season_counts_sorted_by_start(self, report) -> None:
        seasons = [(s.season, s.n_readings) for s in report.seasons]
        assert seasons == [
            ("autumn 2025", 2),
            ("winter 2025/26", 7),
            ("summer 2026", 4),
        ]


class TestWeekdayStats:
    def test_monday_stats(self, report) -> None:
        monday = report.weekdays[0]
        assert monday.weekday == "Mon"
        assert monday.n_readings == 3  # Nov 3, Dec 1, Aug 10
        assert monday.n_distinct_dates == 3
        assert monday.n_days_in_range == 41
        assert monday.readings_per_day == pytest.approx(3 / 41)

    def test_weekday_order_mon_to_sun(self, report) -> None:
        assert [w.weekday for w in report.weekdays] == [
            "Mon",
            "Tue",
            "Wed",
            "Thu",
            "Fri",
            "Sat",
            "Sun",
        ]


class TestHolidayComparison:
    def test_holiday_days_listed_with_counts(self, report) -> None:
        cmp = report.holiday_comparison
        assert cmp.n_holidays == 10  # BW holidays in 2025-11-03..2026-08-12
        by_date = {d.date: d.n_readings for d in cmp.holidays}
        assert by_date[date(2025, 12, 25)] == 3
        assert by_date[date(2025, 12, 26)] == 2
        assert by_date[date(2026, 6, 4)] == 2  # Corpus Christi
        assert by_date[date(2026, 1, 1)] == 0

    def test_rates(self, report) -> None:
        cmp = report.holiday_comparison
        assert cmp.readings_on_holiday_days == 7
        assert cmp.readings_per_day_on_holidays == pytest.approx(7 / 10)
        total_days = (report.date_max - report.date_min).days + 1
        assert total_days == 283
        assert cmp.readings_per_day_on_non_holidays == pytest.approx(6 / 273)

    def test_weekday_matched_ratio_formula(self, report) -> None:
        # Recompute the weekday-matched expectation independently (wiring check):
        # non-holiday weekday rates exclude readings on holiday days.
        cmp = report.holiday_comparison
        weekday_idx = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        holiday_days_per_wd = [0] * 7
        holiday_readings_per_wd = [0] * 7
        for d in cmp.holidays:
            w = weekday_idx.index(d.weekday)
            holiday_days_per_wd[w] += 1
            holiday_readings_per_wd[w] += d.n_readings
        expected = 0.0
        for w, stat in enumerate(report.weekdays):
            n_non_holiday_w = stat.n_days_in_range - holiday_days_per_wd[w]
            if n_non_holiday_w > 0:
                readings_non_w = stat.n_readings - holiday_readings_per_wd[w]
                expected += (readings_non_w / n_non_holiday_w) * holiday_days_per_wd[w]
        assert cmp.weekday_matched_ratio == pytest.approx(7 / expected)
        assert cmp.weekday_matched_ratio > 1


class TestInjectableCalendar:
    def test_explicit_holidays_equal_default(self) -> None:
        readings = _load("synthetic_seasonality.csv")
        start, end = date(2025, 11, 3), date(2026, 8, 12)
        explicit = compute_seasonality(readings, bw_holidays_in_range(start, end))
        assert explicit == compute_seasonality(readings)


class TestEmptyInput:
    def test_empty_readings_raise(self) -> None:
        with pytest.raises(ValueError, match="at least one reading"):
            compute_seasonality([])
