"""Pattern analysis: what do the fill-level data show?"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from .calendar_features import DAILY, day_flags
from .forecast import RateModel


def monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["month"] = d["date"].dt.to_period("M").astype(str)
    g = d.groupby("month")
    out = pd.DataFrame({
        "readings": g.size(),
        "mean_fill_pct": g["fill"].mean(),
        "share_full_100": g["fill"].apply(lambda s: (s >= 100).mean()),
        "share_below_40": g["fill"].apply(lambda s: (s < 40).mean()),
    }).reset_index()
    return out


def weekday_summary(df: pd.DataFrame) -> pd.DataFrame:
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    s = df.groupby(df["date"].dt.dayofweek).size().reindex(range(7), fill_value=0)
    return pd.DataFrame({"weekday": names, "readings": s.to_numpy()})


def material_summary(df: pd.DataFrame, intervals: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("material")
    r = intervals.groupby("material")["rate"].median()
    return pd.DataFrame({
        "containers": g["container"].nunique(),
        "readings": g.size(),
        "mean_fill_pct": g["fill"].mean(),
        "share_full_100": g["fill"].apply(lambda s: (s >= 100).mean()),
        "median_rate_pct_per_day_raw": r,
    }).reset_index()


def calendar_effect(df: pd.DataFrame, intervals: pd.DataFrame) -> pd.DataFrame:
    """Median daily fill rate in cycles that are mostly vacation vs. mostly school time."""
    from .calendar_features import vacation_fraction
    iv = intervals.copy()
    iv["vac"] = vacation_fraction(iv["start"], iv["end"])
    iv["period"] = np.where(iv["vac"] >= 0.5, "mostly school vacation", "mostly school time")
    return (iv.groupby(["material", "period"])["rate"].median().rename("median_rate_pct_per_day")
            .reset_index())


def holiday_weeks(df: pd.DataFrame) -> pd.DataFrame:
    """Readings per week with vacation / holiday flags (shows when the crews were active)."""
    w = df.copy()
    w["week"] = w["date"].dt.to_period("W-SUN").dt.start_time
    flags = day_flags(w["date"])
    w["vac"] = flags["vacation"].to_numpy()
    out = w.groupby("week").agg(readings=("fill", "size"), mean_fill=("fill", "mean"),
                                 vacation_share=("vac", "mean")).reset_index()
    return out


def cluster_sites(model: RateModel, df: pd.DataFrame, k: int = 4, seed: int = 0) -> pd.DataFrame:
    """Group sites with similar behaviour: fill speed per material + how often they overflow."""
    tab = model.container_table()
    piv = tab.pivot(index="site", columns="material", values="log_rate")
    piv = piv.fillna(piv.mean())
    over = df.groupby("site")["fill"].apply(lambda s: (s >= 100).mean()).rename("share_full_100")
    X = piv.join(over).fillna(0.0)
    Z = StandardScaler().fit_transform(X.to_numpy())
    km = KMeans(n_clusters=k, n_init=10, random_state=seed).fit(Z)
    X["cluster_raw"] = km.labels_
    speed = np.exp(piv.mean(axis=1))
    order = speed.groupby(X["cluster_raw"]).mean().sort_values().index.tolist()
    names = {c: f"{i + 1} - " + ["slow", "medium", "fast", "very fast"][min(i, 3)] for i, c in enumerate(order)}
    X["cluster"] = X["cluster_raw"].map(names)
    X["avg_rate_pct_per_day"] = speed
    return X.reset_index().drop(columns="cluster_raw")


def cluster_profile(clusters: pd.DataFrame) -> pd.DataFrame:
    return (clusters.groupby("cluster")
            .agg(sites=("site", "size"), avg_rate_pct_per_day=("avg_rate_pct_per_day", "mean"),
                 share_full_100=("share_full_100", "mean"))
            .reset_index())
