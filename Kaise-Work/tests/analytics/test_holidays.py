"""Tests for src.analytics.holidays — German public holiday calendar.

EXTERNAL CALENDAR INPUT: the expected dates asserted below are public calendar
facts (published German/BW holiday tables), NOT observations from the challenge
dataset. They anchor the deterministic computus implementation; the task brief
supplies Easter Sunday 2026-04-05 and Pentecost Sunday 2026-05-24 as checkable
anchors. Easter 2025-04-20, Easter 2024-03-31 and Easter 2027-03-28 are from
the published Gregorian Easter table.
"""

from datetime import date, timedelta

import pytest

from src.analytics.holidays import (
    HOLIDAY_SCOPE_BW,
    HOLIDAY_SCOPE_NATIONAL,
    bw_holidays_in_range,
    easter_sunday,
    german_holidays_for_year,
    holidays_in_range,
    pentecost_sunday,
)


class TestComputus:
    """Deterministic Anonymous-Gregorian-computus anchors (external facts)."""

    def test_easter_sunday_2026_anchor(self) -> None:
        assert easter_sunday(2026) == date(2026, 4, 5)

    def test_easter_sunday_2025(self) -> None:
        assert easter_sunday(2025) == date(2025, 4, 20)

    def test_easter_sunday_2024(self) -> None:
        assert easter_sunday(2024) == date(2024, 3, 31)

    def test_easter_sunday_2027(self) -> None:
        assert easter_sunday(2027) == date(2027, 3, 28)

    def test_pentecost_sunday_2026_anchor(self) -> None:
        # Pentecost = Easter + 49 days (external calendar fact).
        assert pentecost_sunday(2026) == date(2026, 5, 24)

    def test_pentecost_is_easter_plus_49(self) -> None:
        for year in (2024, 2025, 2026, 2027):
            assert pentecost_sunday(year) == easter_sunday(year) + timedelta(days=49)

    def test_determinism(self) -> None:
        assert easter_sunday(2026) == easter_sunday(2026)


class TestGermanHolidaysForYear:
    """Fixed-date and Easter-derived holidays; scopes national vs BW."""

    def test_national_fixed_dates_2026(self) -> None:
        holidays = {h.name: h.date for h in german_holidays_for_year(2026, HOLIDAY_SCOPE_NATIONAL)}
        assert holidays["new_year"] == date(2026, 1, 1)
        assert holidays["labour_day"] == date(2026, 5, 1)
        assert holidays["german_unity_day"] == date(2026, 10, 3)
        assert holidays["christmas_day"] == date(2026, 12, 25)
        assert holidays["second_christmas_day"] == date(2026, 12, 26)

    def test_national_easter_derived_2026(self) -> None:
        holidays = {h.name: h.date for h in german_holidays_for_year(2026, HOLIDAY_SCOPE_NATIONAL)}
        assert holidays["good_friday"] == date(2026, 4, 3)  # Easter - 2
        assert holidays["easter_monday"] == date(2026, 4, 6)  # Easter + 1
        assert holidays["ascension_day"] == date(2026, 5, 14)  # Easter + 39
        assert holidays["whit_monday"] == date(2026, 5, 25)  # Pentecost + 1

    def test_bw_scope_adds_bw_only_holidays_2026(self) -> None:
        national = {h.name for h in german_holidays_for_year(2026, HOLIDAY_SCOPE_NATIONAL)}
        bw = {h.name: h.date for h in german_holidays_for_year(2026, HOLIDAY_SCOPE_BW)}
        assert {"epiphany_bw", "corpus_christi_bw", "all_saints_bw"} - national == {
            "epiphany_bw",
            "corpus_christi_bw",
            "all_saints_bw",
        }
        assert bw["epiphany_bw"] == date(2026, 1, 6)
        assert bw["corpus_christi_bw"] == date(2026, 6, 4)  # Easter + 60
        assert bw["all_saints_bw"] == date(2026, 11, 1)

    def test_bw_includes_all_national(self) -> None:
        national = {h.name for h in german_holidays_for_year(2026, HOLIDAY_SCOPE_NATIONAL)}
        bw = {h.name for h in german_holidays_for_year(2026, HOLIDAY_SCOPE_BW)}
        assert national <= bw

    def test_sorted_unique_dates(self) -> None:
        holidays = german_holidays_for_year(2026, HOLIDAY_SCOPE_BW)
        dates = [h.date for h in holidays]
        assert dates == sorted(dates)
        assert len(dates) == len(set(dates))

    def test_no_whit_sunday_only_entry(self) -> None:
        # Pentecost Sunday is a Sunday (not an extra working-day holiday entry);
        # the calendar lists Whit Monday instead.
        names = {h.name for h in german_holidays_for_year(2026, HOLIDAY_SCOPE_BW)}
        assert "pentecost_sunday" not in names
        assert "whit_monday" in names


class TestHolidaysInRange:
    """Range filtering; counts below are external calendar facts, not data."""

    def test_bw_holidays_in_dataset_range(self) -> None:
        # Dataset span (docs/data_profile.md §6): 2025-10-17 .. 2026-09-30.
        start, end = date(2025, 10, 17), date(2026, 9, 30)
        holidays = bw_holidays_in_range(start, end)
        dates = [h.date for h in holidays]
        assert len(holidays) == 11  # counted from the published BW 2025/26 tables
        assert date(2025, 11, 1) in dates  # All Saints (BW)
        assert date(2025, 12, 25) in dates and date(2025, 12, 26) in dates
        assert date(2026, 1, 6) in dates  # Epiphany (BW)
        assert date(2026, 6, 4) in dates  # Corpus Christi (BW)

    def test_excludes_out_of_range(self) -> None:
        holidays = bw_holidays_in_range(date(2026, 3, 1), date(2026, 4, 30))
        assert {h.name for h in holidays} == {"good_friday", "easter_monday"}

    def test_inclusive_bounds(self) -> None:
        holidays = holidays_in_range(date(2026, 5, 24), date(2026, 5, 25), HOLIDAY_SCOPE_BW)
        assert [h.name for h in holidays] == ["whit_monday"]

    def test_empty_range(self) -> None:
        assert holidays_in_range(date(2026, 2, 1), date(2026, 2, 28), HOLIDAY_SCOPE_BW) == ()


@pytest.mark.parametrize(
    ("year", "expected"),
    [(2024, date(2024, 3, 31)), (2025, date(2025, 4, 20)), (2026, date(2026, 4, 5))],
)
def test_easter_table(year: int, expected: date) -> None:
    assert easter_sunday(year) == expected
