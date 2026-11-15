"""Run the full evaluation and write results/ (used by the dashboard).

    python run_backtest.py            # forecast metrics + frontier + routed backtest (~10 min)
    python run_backtest.py --fast     # skip the routed runs (~2 min)
    python run_backtest.py --only dynamic_same_service   # re-run one routed scenario
"""
from __future__ import annotations
import argparse, json, os, sys, time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from dataclasses import replace

from fillinq.config import load_settings
from fillinq.data import load_readings, build_intervals, quality_report
from fillinq.forecast import RateModel, cross_validate, forward_test
from fillinq.geo import get_locations
from fillinq.simulate import Twin, run_baseline, run_policy

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "glass_fill_levels.csv")
LOCS = os.path.join(HERE, "data", "site_locations.csv")
OUT = os.path.join(HERE, "results")
START, END = "2026-04-01", "2026-09-30"
PLANNER_TRAIN_END = "2026-04-01"
SCENARIOS = {
    "baseline_replay": None,
    "dynamic_same_service": 0.82,   # tuned: same overflow-days as the historical schedule
    "dynamic_same_effort": 0.70,    # tuned: about the same number of site visits
    # routed runs serve mandatory stops only (opt_p=1.01) so that distance is compared like for like
}


def _setup():
    df = load_readings(DATA)
    iv = build_intervals(df)
    truth = RateModel().fit(iv)
    tw = Twin(truth, df, start=START, end=END)
    planner = RateModel().fit(iv[iv["end"] < PLANNER_TRAIN_END])
    locs, synthetic = get_locations(df["site"].unique(), LOCS)
    return df, iv, truth, tw, planner, locs, synthetic


def _routed(args):
    name, p, time_limit = args
    df, iv, truth, tw, planner, locs, _ = _setup()
    cfg = replace(load_settings(), opt_p=1.01)
    t = time.time()
    if p is None:
        r = run_baseline(tw, locs, cfg, route=True, time_limit=time_limit)
    else:
        r = run_policy(tw, planner, cfg, locs, route=True, time_limit=time_limit, must_p=p)
    daily = r.pop("daily")
    daily.to_csv(os.path.join(OUT, f"daily_{name}.csv"), index=False)
    r.update(name=name, km=float(daily["km"].sum()), hours=float(daily["hours"].sum()),
             truck_days=int(daily["trucks"].sum()), seconds=round(time.time() - t))
    return r


def _write_meta(synthetic):
    st = load_settings().to_dict()
    st["working_weekdays"] = list(st["working_weekdays"])
    json.dump({"engine_revision": 2, "synthetic_locations": bool(synthetic), "start": START, "end": END,
               "planner_train_end": PLANNER_TRAIN_END, "scenarios": SCENARIOS, "settings": st},
              open(os.path.join(OUT, "meta.json"), "w"), indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--time-limit", type=int, default=3)
    ap.add_argument("--only", default="", help="comma-separated scenario names to (re)run; keeps other results")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if a.only:
        names = [n for n in a.only.split(",") if n]
        jobs = [(n, SCENARIOS[n], a.time_limit) for n in names]
        with ProcessPoolExecutor(max_workers=min(3, len(jobs))) as ex:
            res = list(ex.map(_routed, jobs))
        path = os.path.join(OUT, "routed_summary.csv")
        old = pd.read_csv(path) if os.path.exists(path) else pd.DataFrame()
        old = old[~old["name"].isin(names)] if len(old) else old
        pd.concat([old, pd.DataFrame(res)]).to_csv(path, index=False)
        print(pd.DataFrame(res).T.to_string())
        _write_meta(not os.path.exists(LOCS))
        return
    df, iv, truth, tw, planner, locs, synthetic = _setup()
    json.dump(quality_report(df), open(os.path.join(OUT, "quality.json"), "w"), indent=2)

    # 1. forecast quality on held-out readings
    cv = cross_validate(iv)
    fm = {"cross_validation_mean": cv.mean().to_dict(), "forward_test": forward_test(iv),
          "model": truth.summary()}
    json.dump(fm, open(os.path.join(OUT, "forecast_metrics.json"), "w"), indent=2, default=float)
    print("forecast metrics done", flush=True)

    # 2. frontier: visits vs overflow for many thresholds (no routing)
    cfg = load_settings()
    base = run_baseline(tw); base.pop("daily")
    rows = [dict(policy="historical schedule", threshold=np.nan, **base)]
    for name, pl in (("dynamic (model trained until Mar)", planner), ("dynamic (model trained on all data)", truth)):
        for p in (0.97, 0.92, 0.88, 0.82, 0.76, 0.70, 0.64, 0.58, 0.50, 0.42, 0.35, 0.28, 0.2):
            r = run_policy(tw, pl, cfg, must_p=p); r.pop("daily")
            rows.append(dict(policy=name, threshold=p, **r))
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "frontier.csv"), index=False)
    print("frontier done", flush=True)

    # 3. routed backtest (illustrative coordinates unless site_locations.csv is given)
    if not a.fast:
        jobs = [(n, p, a.time_limit) for n, p in SCENARIOS.items()]
        with ProcessPoolExecutor(max_workers=3) as ex:
            res = list(ex.map(_routed, jobs))
        pd.DataFrame(res).to_csv(os.path.join(OUT, "routed_summary.csv"), index=False)
        print(pd.DataFrame(res).T.to_string())
    _write_meta(synthetic)


if __name__ == "__main__":
    main()
