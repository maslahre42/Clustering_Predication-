"""Which containers should be emptied today? (selection step before routing)

For every container the forecast gives P(overflow within the look-ahead window).
  * due bin     : that probability >= must_p            -> its site is a MANDATORY stop
  * extra bins  : at a visited site we also empty bins that are likely full soon
  * optional    : sites with some risk but nothing urgent become OPTIONAL stops;
                  the router includes them only if the detour is cheap enough.
"""
from __future__ import annotations
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import OpsConfig
from .forecast import RateModel
from .routing import site_demand


def assess_bins(model: RateModel, state: pd.DataFrame, date, cfg: OpsConfig) -> pd.DataFrame:
    """state: columns container, site, material, last_empty (Timestamp).
    Returns one row per bin with expected fill today and overflow risk."""
    date = pd.Timestamp(date)
    n = len(state)
    now = model.predict(state["container"], state["last_empty"], pd.DatetimeIndex([date] * n), thresholds=(90, 100))
    fut_date = date + pd.Timedelta(days=cfg.lookahead_days)
    fut = model.predict(state["container"], state["last_empty"], pd.DatetimeIndex([fut_date] * n), thresholds=(100,))
    out = state[["container", "site", "material", "last_empty"]].reset_index(drop=True).copy()
    out["fill_now"] = now["mean_fill"].to_numpy()
    out["p_over_now"] = now["p_ge_100"].to_numpy()
    out["p_over_window"] = fut["p_ge_100"].to_numpy()
    out["days_since_empty"] = now["days"].to_numpy()
    return out


def select_stops(bins: pd.DataFrame, locs: pd.DataFrame | None, cfg: OpsConfig,
                 must_p: float | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (stops, bins_to_empty). `stops` has the columns plan_routes() needs
    (lat/lon only if `locs` is given)."""
    must_p = cfg.must_p if must_p is None else must_p
    b = bins.copy()
    b["due"] = b["p_over_window"] >= must_p
    site_due = b.groupby("site")["due"].transform("max")
    site_risk = b.groupby("site")["p_over_window"].transform("max")
    extra = (b["p_over_window"] >= cfg.bin_p_collect) | (b["fill_now"] >= cfg.bin_fill_collect)
    b["collect"] = (b["due"] | (site_due & extra) | (~site_due & extra & (site_risk >= cfg.opt_p)))
    # a non-due site is only worth a stop if it carries some real risk
    b["site_must"] = site_due
    b["site_value"] = site_risk
    take = b[b["collect"]].copy()
    if take.empty:
        return pd.DataFrame(columns=["site", "lat", "lon", "vol_l", "kg", "n_bins", "must", "value"]), take
    dem = site_demand(take.rename(columns={"fill_now": "fill"}), cfg)
    agg = take.groupby("site").agg(n_bins=("container", "size"), must=("site_must", "max"), value=("site_value", "max"))
    stops = agg.join(dem).reset_index()
    if locs is not None:
        stops = stops.merge(locs[["site", "lat", "lon"]], on="site", how="left")
    return stops, take
