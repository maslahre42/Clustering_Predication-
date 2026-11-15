"""German public holiday calendar via deterministic computus.

EXTERNAL CALENDAR INPUT — not derived from the challenge dataset. All dates in
this module are public-calendar facts (German federal and Baden-Württemberg
holiday law); they enter analysis only as calendar metadata. Region ``bw`` is
used because the challenge is the PreZero/Heilbronn challenge (Heilbronn is in
Baden-Württemberg).

Easter is computed with the Anonymous Gregorian algorithm (deterministic, no
dependencies). Anchors checked in tests: Easter Sunday 2026-04-05, Pentecost
Sunday 2026-05-24 (task brief) plus published dates for 2024/2025/2027.

School vacations (BW) are deliberately NOT implemented here: their dates could
not be verified from local knowledge, so they remain an open question
(docs/eda_report.md) and only public holidays are analysed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final, Literal

HolidayScope = Literal["national", "bw"]

HOLIDAY_SCOPE_NATIONAL: Final = "national"
HOLIDAY_SCOPE_BW: Final = "bw"
"""Baden-Württemberg (challenge region Heilbronn): national + BW-only days."""

# Offset definitions relative to Easter Sunday (days); external calendar facts.
_EASTER_OFFSETS: Final[dict[str, int]] = {
    "good_friday": -2,
    "easter_monday": 1,
    "ascension_day": 39,
    "whit_monday": 50,  # Pentecost Sunday is Easter + 49; Whit Monday + 50
    "corpus_christi_bw": 60,
}

# Fixed-date holidays; (month, day) -> (name, scope).
_FIXED: Final[dict[tuple[int, int], tuple[str, HolidayScope]]] = {
    (1, 1): ("new_year", HOLIDAY_SCOPE_NATIONAL),
    (1, 6): ("epiphany_bw", HOLIDAY_SCOPE_BW),
    (5, 1): ("labour_day", HOLIDAY_SCOPE_NATIONAL),
    (10, 3): ("german_unity_day", HOLIDAY_SCOPE_NATIONAL),
    (11, 1): ("all_saints_bw", HOLIDAY_SCOPE_BW),
    (12, 25): ("christmas_day", HOLIDAY_SCOPE_NATIONAL),
    (12, 26): ("second_christmas_day", HOLIDAY_SCOPE_NATIONAL),
}


@dataclass(frozen=True)
class GermanHoliday:
    """One public holiday occurrence (external calendar input, not dataset)."""

    date: date
    name: str
    scope: HolidayScope


def easter_sunday(year: int) -> date:
    """Gregorian Easter Sunday via the Anonymous Gregorian algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741  # `l` is the algorithm's standard letter
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def pentecost_sunday(year: int) -> date:
    """Pentecost (Whit) Sunday = Easter Sunday + 49 days."""
    return easter_sunday(year) + timedelta(days=49)


def german_holidays_for_year(
    year: int, scope: HolidayScope = HOLIDAY_SCOPE_BW
) -> tuple[GermanHoliday, ...]:
    """All public holidays for one year, sorted by date, unique dates.

    ``national`` = federal holidays; ``bw`` = national + BW-only days
    (Epiphany, Corpus Christi, All Saints). Easter Sunday and Pentecost Sunday
    fall on Sundays and are therefore not separate entries.
    """
    easter = easter_sunday(year)
    result: list[GermanHoliday] = []
    for (month, day), (name, holiday_scope) in _FIXED.items():
        result.append(GermanHoliday(date(year, month, day), name, holiday_scope))
    for name, offset in _EASTER_OFFSETS.items():
        holiday_scope = HOLIDAY_SCOPE_BW if name.endswith("_bw") else HOLIDAY_SCOPE_NATIONAL
        result.append(GermanHoliday(easter + timedelta(days=offset), name, holiday_scope))
    if scope == HOLIDAY_SCOPE_NATIONAL:
        result = [h for h in result if h.scope == HOLIDAY_SCOPE_NATIONAL]
    result.sort(key=lambda h: h.date)
    return tuple(result)


def holidays_in_range(
    start: date, end: date, scope: HolidayScope = HOLIDAY_SCOPE_BW
) -> tuple[GermanHoliday, ...]:
    """Sorted, unique public holidays with ``start <= date <= end`` (inclusive)."""
    if start > end:
        return ()
    years = range(start.year, end.year + 1)
    return tuple(
        holiday
        for year in years
        for holiday in german_holidays_for_year(year, scope)
        if start <= holiday.date <= end
    )


def bw_holidays_in_range(start: date, end: date) -> tuple[GermanHoliday, ...]:
    """Public holidays in Baden-Württemberg (challenge region) within range."""
    return holidays_in_range(start, end, HOLIDAY_SCOPE_BW)
