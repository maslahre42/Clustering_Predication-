import io
import numpy as np
import pandas as pd
import pytest

from fillinq.config import OpsConfig
from fillinq.data import load_readings, build_intervals
from fillinq.forecast import RateModel
from fillinq.geo import synthetic_locations
from fillinq.routing import plan_routes

CSV = """﻿Location_id,material_type,date,fill_level_perc
a,white,2026-01-01,50
a,white,2026-01-11,overfull
a,white,2026-01-21,100
b,green,2026-01-01,20
b,green,2026-02-01,0
"""


def test_loader_handles_bom_overfull_and_censoring():
    df = load_readings(io.StringIO(CSV))
    assert set(df["material"]) == {"white", "green"}
    assert df["censored"].sum() == 2          # overfull and 100
    assert df["fill"].max() == 100


def test_intervals_rate_and_gap():
    iv = build_intervals(load_readings(io.StringIO(CSV)))
    row = iv[(iv["site"] == "a") & (iv["gap"] == 10)].iloc[0]
    assert row["rate"] == pytest.approx(10.0)  # 100 / 10 days, a lower bound
    assert len(iv) == 3


def _synthetic_intervals(n_sites=40, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_sites):
        rate = np.exp(rng.normal(0.5, 0.6))
        d = pd.Timestamp("2026-01-01")
        for _ in range(8):
            gap = int(rng.integers(10, 50))
            d2 = d + pd.Timedelta(days=gap)
            fill = min(100.0, rate * gap * np.exp(rng.normal(0, 0.4)))
            rows.append(("s%d" % s, "white", d2, fill))
            d = d2
    df = pd.DataFrame(rows, columns=["site", "material", "date", "fill"])
    df["censored"] = df["fill"] >= 100
    df["container"] = df["site"] + "|" + df["material"]
    df["fill"] = df["fill"].round(-1).clip(10, 100)
    first = df.groupby("container").head(1).copy()
    first["date"] -= pd.Timedelta(days=20)
    return build_intervals(pd.concat([first, df]).sort_values(["container", "date"]))


def test_forecast_is_monotone_and_bounded():
    m = RateModel().fit(_synthetic_intervals())
    days = pd.date_range("2026-03-01", periods=30)
    p = m.predict(np.array(["s1|white"] * 30), pd.DatetimeIndex([days[0]] * 30), days)
    assert (p["mean_fill"].diff().dropna() >= -1e-9).all()
    assert p["mean_fill"].between(0, 100).all()
    assert (p["p_ge_100"].diff().dropna() >= -1e-9).all()


def _stops(n=12, seed=3):
    cfg = OpsConfig()
    loc = synthetic_locations([f"s{i}" for i in range(n)])
    rng = np.random.default_rng(seed)
    nb = rng.integers(1, 4, n)
    vol = nb * 2200.0
    return cfg, pd.DataFrame({"site": loc["site"], "lat": loc["lat"], "lon": loc["lon"], "vol_l": vol,
                              "kg": vol * cfg.glass_density_t_m3, "n_bins": nb, "must": True, "value": 1.0})


def test_routes_respect_capacity_and_serve_all_mandatory():
    cfg, st = _stops()
    plan = plan_routes(st, cfg, time_limit_s=2)
    assert not plan.dropped_mandatory
    served = {s for r in plan.routes for s, _, _ in r["stops"]}
    assert served == set(st["site"])
    for r in plan.routes:
        assert r["hours"] <= cfg.shift_hours + 1e-6
        for t in r["trips"]:
            assert t["volume_m3"] <= cfg.truck_volume_m3 + 1e-6
            assert t["weight_t"] <= cfg.truck_payload_t + 1e-6


def test_empty_input_gives_empty_plan():
    plan = plan_routes(pd.DataFrame(columns=["site", "lat", "lon", "vol_l", "kg", "n_bins", "must", "value"]), OpsConfig())
    assert plan.kpis["trucks"] == 0
