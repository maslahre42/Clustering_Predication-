"""Loading, cleaning and quality checks for Fillinq fill-level readings.

Input columns (as delivered by PreZero):
    Location_id, material_type, date, fill_level_perc
fill_level_perc is a multiple of 10 (10..100) or the text "overfull".

Key modelling assumption (to be confirmed with PreZero):
    a reading is taken when the container is visited, BEFORE emptying,
    and the container is emptied during that visit.
Under this assumption the time between two readings of the same container
is one filling cycle, and "fill / days" is the daily fill rate of that cycle.
Readings of 100 or "overfull" are *censored*: the true fill is at least 100.
"""
from __future__ import annotations
from __future__ import annotations

import io
import pandas as pd
import numpy as np

COLUMN_ALIASES = {
    "location_id": "site", "site": "site", "location": "site",
    "material_type": "material", "material": "material",
    "date": "date",
    "fill_level_perc": "fill_raw", "fill_level": "fill_raw", "fill": "fill_raw",
}

MIN_FILL_FLOOR = 2.5  # a reading of 0 is treated as "a few percent" to keep logs finite


def load_readings(src) -> pd.DataFrame:
    """Read a CSV path or file-like object and return a clean readings table."""
    if hasattr(src, "read"):
        raw = src.read()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8-sig")
        df = pd.read_csv(io.StringIO(raw), sep=None, engine="python")
    else:
        df = pd.read_csv(src, sep=None, engine="python", encoding="utf-8-sig")
    df.columns = [str(c).strip().lstrip("﻿") for c in df.columns]
    rename = {c: COLUMN_ALIASES[c.lower()] for c in df.columns if c.lower() in COLUMN_ALIASES}
    df = df.rename(columns=rename)
    missing = {"site", "material", "date", "fill_raw"} - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}. Found: {list(df.columns)}")
    df = df[["site", "material", "date", "fill_raw"]].copy()
    df["site"] = df["site"].astype(str).str.strip()
    df["material"] = df["material"].astype(str).str.strip().str.lower()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    txt = df["fill_raw"].astype(str).str.strip().str.lower()
    df["overfull"] = txt.eq("overfull")
    df["fill"] = pd.to_numeric(txt.where(~df["overfull"], "100"), errors="coerce")
    df = df.dropna(subset=["site", "material", "date", "fill"])
    df["fill"] = df["fill"].clip(0, 100)
    df["censored"] = df["fill"] >= 100.0
    df = df.drop(columns="fill_raw")
    df = df.drop_duplicates(["site", "material", "date"], keep="last")
    df["container"] = df["site"] + "|" + df["material"]
    return df.sort_values(["container", "date"]).reset_index(drop=True)


def quality_report(df: pd.DataFrame) -> dict:
    g = df.groupby("container")
    gaps = df.groupby("container")["date"].diff().dt.days.dropna()
    return {
        "readings": int(len(df)),
        "sites": int(df["site"].nunique()),
        "containers": int(df["container"].nunique()),
        "materials": df["material"].value_counts().to_dict(),
        "date_min": df["date"].min().date().isoformat(),
        "date_max": df["date"].max().date().isoformat(),
        "readings_per_container_median": float(g.size().median()),
        "gap_days_median": float(gaps.median()) if len(gaps) else float("nan"),
        "gap_days_p90": float(gaps.quantile(0.9)) if len(gaps) else float("nan"),
        "share_at_or_over_100": float((df["fill"] >= 100).mean()),
        "share_overfull": float(df["overfull"].mean()),
        "share_le_50": float((df["fill"] <= 50).mean()),
        "share_ge_90": float((df["fill"] >= 90).mean()),
        "mean_fill_at_visit": float(df["fill"].mean()),
        "weekend_readings": int((df["date"].dt.dayofweek >= 5).sum()),
        "has_coordinates": False,
    }


def build_intervals(df: pd.DataFrame) -> pd.DataFrame:
    """One row per filling cycle (previous reading -> this reading)."""
    d = df.sort_values(["container", "date"]).copy()
    d["start"] = d.groupby("container")["date"].shift(1)
    d = d.dropna(subset=["start"]).copy()
    d["gap"] = (d["date"] - d["start"]).dt.days.clip(lower=1).astype(int)
    d["end"] = d["date"]
    d["rate"] = d["fill"].clip(lower=MIN_FILL_FLOOR) / d["gap"]  # % per day (lower bound if censored)
    return d[["container", "site", "material", "start", "end", "gap", "fill", "censored", "rate"]].reset_index(drop=True)
