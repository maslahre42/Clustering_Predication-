"""Backtest: fixed (historical) schedule vs. dynamic forecast-driven collection.

A "digital twin" generates the true fill level of every container:
    daily rate = exp(a_c + month effect + vacation effect)  (from the model fitted on ALL data)
    each filling cycle gets its own random multiplier exp(sigma * eps)   (common random numbers,
    so both policies face exactly the same random world).

* BASELINE replays the real collection calendar of the data (same sites, same days).
* DYNAMIC  plans each weekday with only what a planner would know: the date a container was
  last emptied and a forecast model trained on data up to `planner_train_end`.

Both policies are scored on the same true fill levels.
Honest limits: the twin shares its structure with the forecast model, and the real data
only has readings at visits, so absolute numbers are indicative; the comparison between
policies is what matters. Distances and hours use illustrative site coordinates.
"""
from __future__ import annotations
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import OpsConfig
from .forecast import RateModel
from .policy import assess_bins, select_stops
from .routing import plan_routes, site_demand

K_CYCLES = 60


class Twin:
    def __init__(self, truth: RateModel, readings: pd.DataFrame, start="2026-04-01", end="2026-09-30", seed=7):
        self.truth = truth
        self.start, self.end = pd.Timestamp(start), pd.Timestamp(end)
        self.day0 = pd.Timestamp(readings["date"].min())
        self.days = pd.date_range(self.day0, self.end, freq="D")
        self.readings = readings
        cont = (readings[["container", "site", "material"]].drop_duplicates("container")
                .sort_values("container").reset_index(drop=True))
        self.cont = cont
        self.cid = {c: i for i, c in enumerate(cont["container"])}
        n = len(cont)
        # container effect for the twin: model value, or material mean if unseen
        a = np.empty(n)
        for i, (c, m) in enumerate(zip(cont["container"], cont["material"])):
            j = truth.cidx.get(c)
            a[i] = truth.a[j] if j is not None else truth.m[truth.midx[m]]
        season = truth.b[self.days.month.to_numpy() - 1] + truth.g * __import__("fillinq.calendar_features", fromlist=["DAILY"]).DAILY["vacation"].reindex(self.days).fillna(0).to_numpy()
        daily = np.exp(a[:, None] + season[None, :])
        self.CR = np.cumsum(daily, axis=1)
        rng = np.random.default_rng(seed)
        self.mult = np.exp(truth.sigma * rng.standard_normal((n, K_CYCLES)))
        self.day_index = {d: i for i, d in enumerate(self.days)}

    # initial state at the start of the simulation (same for every policy)
    def initial_state(self):
        r = self.readings[self.readings["date"] < self.start]
        last = r.groupby("container")["date"].max()
        le = self.cont["container"].map(last).fillna(self.day0)
        return np.array([self.day_index[pd.Timestamp(d)] for d in le]), np.zeros(len(self.cont), dtype=int)

    def true_fill(self, c, t, le, k):
        return (self.CR[c, t] - self.CR[c, le[c]]) * self.mult[c, k[c]]

    def overflow_days(self, c, t, le, k):
        need = self.CR[c, le[c]] + 100.0 / self.mult[c, k[c]]
        cross = np.array([np.searchsorted(self.CR[ci], nd, side="left") for ci, nd in zip(c, need)])
        return np.maximum(0, t - cross)


def _kpis(rec: dict, n_days: int) -> dict:
    f = np.array(rec["fill"]) if rec["fill"] else np.array([0.0])
    return {
        "site_visits": int(rec["stops"]),
        "bin_collections": int(len(rec["fill"])),
        "mean_fill_at_collection_pct": float(np.minimum(f, 100).mean()),
        "share_collections_below_40pct": float((f < 40).mean()),
        "share_collections_at_or_over_100pct": float((f >= 100).mean()),
        "overflow_bin_days": float(rec["overflow_days"]),
        "overflow_events": int(rec["overflow_events"]),
    }


def _new_rec():
    return {"stops": 0, "fill": [], "overflow_days": 0.0, "overflow_events": 0}


def _close_open_cycles(tw: Twin, le, k, rec, t_end):
    c = np.arange(len(le))
    t = np.full(len(le), t_end)
    od = tw.overflow_days(c, t, le, k)
    rec["overflow_days"] += float(od.sum())
    rec["overflow_events"] += int((tw.true_fill(c, t, le, k) >= 100).sum())


def _collect(tw: Twin, idx, t, le, k, rec):
    idx = np.asarray(idx, dtype=int)
    if len(idx) == 0:
        return
    tt = np.full(len(idx), t)
    f = tw.true_fill(idx, tt, le, k)
    rec["fill"].extend(f.tolist())
    rec["overflow_days"] += float(tw.overflow_days(idx, tt, le, k).sum())
    rec["overflow_events"] += int((f >= 100).sum())
    le[idx] = t
    k[idx] = np.minimum(k[idx] + 1, K_CYCLES - 1)


def _stop_table(tw: Twin, idx, fills, locs, cfg, must=True, value=1.0):
    d = tw.cont.iloc[idx][["container", "site", "material"]].copy()
    d["fill"] = np.minimum(fills, 100)
    dem = site_demand(d, cfg)
    agg = d.groupby("site").size().rename("n_bins")
    st = agg.to_frame().join(dem).reset_index()
    st["must"] = must
    st["value"] = value
    return st.merge(locs[["site", "lat", "lon"]], on="site", how="left")


def run_baseline(tw: Twin, locs=None, cfg: OpsConfig | None = None, route=False, time_limit=2) -> dict:
    """Replay the real calendar between start and end."""
    cfg = cfg or OpsConfig()
    le, k = tw.initial_state()
    rec = _new_rec()
    real = tw.readings[(tw.readings["date"] >= tw.start) & (tw.readings["date"] <= tw.end)]
    daily = []
    for date, grp in real.groupby("date"):
        t = tw.day_index[date]
        idx = np.array([tw.cid[c] for c in grp["container"]])
        f = tw.true_fill(idx, np.full(len(idx), t), le, k)
        rec["stops"] += grp["site"].nunique()
        row = {"date": date, "stops": int(grp["site"].nunique()), "bins": int(len(idx))}
        if route:
            plan = plan_routes(_stop_table(tw, idx, f, locs, cfg), cfg, time_limit_s=time_limit)
            row.update(km=plan.kpis["km"], hours=plan.kpis["hours"], trucks=plan.kpis["trucks"])
        daily.append(row)
        _collect(tw, idx, t, le, k, rec)
    _close_open_cycles(tw, le, k, rec, tw.day_index[tw.end])
    out = _kpis(rec, len(daily))
    out["daily"] = pd.DataFrame(daily)
    return out


def run_policy(tw: Twin, planner: RateModel, cfg: OpsConfig, locs=None, route=False,
               time_limit=2, must_p=None, progress=None) -> dict:
    """Dynamic policy on every weekday between start and end."""
    le, k = tw.initial_state()
    rec = _new_rec()
    state_base = tw.cont[["container", "site", "material"]].copy()
    daily = []
    weekdays = [d for d in pd.date_range(tw.start, tw.end, freq="D") if d.dayofweek in cfg.working_weekdays]
    for n_d, date in enumerate(weekdays):
        t = tw.day_index[date]
        state = state_base.copy()
        state["last_empty"] = tw.days[le]
        bins = assess_bins(planner, state, date, cfg)
        stops, take = select_stops(bins, locs if route else None, cfg, must_p=must_p)
        if stops.empty:
            continue
        if route:
            plan = plan_routes(stops, cfg, time_limit_s=time_limit)
            visited = set(s for r in plan.routes for s, _, _ in r["stops"])
            take = take[take["site"].isin(visited)]
            row = {"date": date, "stops": len(visited), "bins": len(take),
                   "km": plan.kpis["km"], "hours": plan.kpis["hours"], "trucks": plan.kpis["trucks"],
                   "dropped_mandatory": len(plan.dropped_mandatory)}
        else:
            take = take[take["site_must"]]  # without routing only mandatory sites are served
            row = {"date": date, "stops": int(take["site"].nunique()), "bins": len(take)}
        idx = np.array([tw.cid[c] for c in take["container"]], dtype=int)
        rec["stops"] += row["stops"]
        daily.append(row)
        _collect(tw, idx, t, le, k, rec)
        if progress and n_d % 10 == 0:
            progress(n_d, len(weekdays))
    _close_open_cycles(tw, le, k, rec, tw.day_index[tw.end])
    out = _kpis(rec, len(daily))
    out["daily"] = pd.DataFrame(daily)
    return out
