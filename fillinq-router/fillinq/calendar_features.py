"""Public holidays and school vacations (Baden-Württemberg).

Holidays come from the `holidays` package. School vacations are listed
explicitly below (source: Kultusministerium Baden-Württemberg calendar,
cross-checked against several calendar sites). Update this list for
other years or regions - it is the only place that needs to change.
"""
from __future__ import annotations
from __future__ import annotations

import numpy as np
import pandas as pd

try:
    import holidays as _holidays
except ImportError:  # keep the package usable without the optional dependency
    _holidays = None

SCHOOL_VACATIONS = [
    ("Sommerferien 2025", "2025-07-31", "2025-09-13"),
    ("Herbstferien 2025", "2025-10-27", "2025-10-31"),
    ("Weihnachtsferien 2025/26", "2025-12-22", "2026-01-05"),
    ("Osterferien 2026", "2026-03-30", "2026-04-11"),
    ("Pfingstferien 2026", "2026-05-26", "2026-06-05"),
    ("Sommerferien 2026", "2026-07-30", "2026-09-12"),
    ("Herbstferien 2026", "2026-10-26", "2026-10-31"),
    ("Weihnachtsferien 2026/27", "2026-12-23", "2027-01-09"),
]

_START = pd.Timestamp("2025-01-01")
_END = pd.Timestamp("2027-12-31")


def _build_daily() -> pd.DataFrame:
    days = pd.date_range(_START, _END, freq="D")
    df = pd.DataFrame(index=days)
    df["vacation"] = 0.0
    df["vacation_name"] = ""
    for name, a, b in SCHOOL_VACATIONS:
        mask = (df.index >= a) & (df.index <= b)
        df.loc[mask, "vacation"] = 1.0
        df.loc[mask, "vacation_name"] = name
    df["holiday"] = 0.0
    df["holiday_name"] = ""
    if _holidays is not None:
        hol = _holidays.Germany(subdiv="BW", years=range(_START.year, _END.year + 1))
        for d, n in hol.items():
            ts = pd.Timestamp(d)
            if ts in df.index:
                df.loc[ts, "holiday"] = 1.0
                df.loc[ts, "holiday_name"] = n
    df["vac_cum"] = df["vacation"].cumsum()
    df["hol_cum"] = df["holiday"].cumsum()
    return df


DAILY = _build_daily()


def day_flags(dates) -> pd.DataFrame:
    """Vacation / holiday flags for a set of dates."""
    idx = pd.DatetimeIndex(pd.to_datetime(dates)).normalize()
    return DAILY.reindex(idx)[["vacation", "vacation_name", "holiday", "holiday_name"]]


def vacation_fraction(start, end) -> np.ndarray:
    """Share of days in (start, end] that are school vacation. Vectorised."""
    s = pd.DatetimeIndex(pd.to_datetime(start)).normalize()
    e = pd.DatetimeIndex(pd.to_datetime(end)).normalize()
    vc = DAILY["vac_cum"]
    vs = vc.reindex(s).to_numpy()
    ve = vc.reindex(e).to_numpy()
    n = np.maximum((e - s).days.to_numpy(), 1)
    out = (ve - vs) / n
    return np.nan_to_num(out, nan=0.0)


def holiday_count(start, end) -> np.ndarray:
    s = pd.DatetimeIndex(pd.to_datetime(start)).normalize()
    e = pd.DatetimeIndex(pd.to_datetime(end)).normalize()
    hc = DAILY["hol_cum"]
    return np.nan_to_num(hc.reindex(e).to_numpy() - hc.reindex(s).to_numpy(), nan=0.0)
