"""WasteRouting.AI - dashboard for fill-level analysis, forecast and route planning.

Run:  streamlit run app.py
"""
from __future__ import annotations
import json
import os

import folium
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

from fillinq.calendar_features import DAILY
from fillinq.config import MATERIALS, OpsConfig
from fillinq.data import build_intervals, load_readings, quality_report
from fillinq.forecast import RateModel
from fillinq.geo import get_locations
from fillinq.patterns import (calendar_effect, cluster_profile, cluster_sites, material_summary,
                              monthly_summary, weekday_summary)
from fillinq.policy import assess_bins, select_stops
from fillinq.routing import plan_routes

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA = os.path.join(HERE, "data", "glass_fill_levels.csv")
DEFAULT_LOCS = os.path.join(HERE, "data", "site_locations.csv")
RESULTS = os.path.join(HERE, "results")

st.set_page_config(page_title="WasteRouting.AI", page_icon="♻️", layout="wide")


# ----------------------------------------------------------------- caching
@st.cache_data(show_spinner="Reading data ...")
def _load(data_bytes: bytes | None):
    import io
    src = io.BytesIO(data_bytes) if data_bytes else DEFAULT_DATA
    df = load_readings(src)
    return df, build_intervals(df), quality_report(df)


@st.cache_resource(show_spinner="Fitting the fill-rate model ...")
def _model(_intervals, key):
    return RateModel().fit(_intervals)


@st.cache_data(show_spinner=False)
def _clusters(_model_obj, _df, key, k):
    return cluster_sites(_model_obj, _df, k=k)


def _results(name):
    p = os.path.join(RESULTS, name)
    if not os.path.exists(p):
        return None
    return json.load(open(p)) if name.endswith(".json") else pd.read_csv(p)


# ----------------------------------------------------------------- sidebar
st.sidebar.title("♻️ WasteRouting.AI")
PAGES = ["1 Data", "2 Patterns", "3 Forecast", "4 Route planner", "5 Backtest", "6 Guide"]
_q = st.query_params.get("page", "1")
_start = int(_q) - 1 if str(_q).isdigit() and 1 <= int(_q) <= len(PAGES) else 0
page = st.sidebar.radio("Page", PAGES, index=_start)
up = st.sidebar.file_uploader("Fill-level CSV (optional)", type="csv",
                              help="Columns: Location_id, material_type, date, fill_level_perc. Default: bundled PreZero file.")
up_loc = st.sidebar.file_uploader("Site locations CSV (optional)", type="csv", help="Columns: site, lat, lon")
data_bytes = up.getvalue() if up else None
df, iv, qual = _load(data_bytes)
data_key = f"{len(df)}-{df['date'].max()}-{hash(data_bytes) if data_bytes else 0}"
model = _model(iv, data_key)

if up_loc is not None:
    import io
    tmp = pd.read_csv(io.BytesIO(up_loc.getvalue()))
    tmp.to_csv(os.path.join(HERE, "data", "_uploaded_locations.csv"), index=False)
    loc_path = os.path.join(HERE, "data", "_uploaded_locations.csv")
else:
    loc_path = DEFAULT_LOCS
locs, synthetic = get_locations(df["site"].unique(), loc_path)
if synthetic:
    st.sidebar.warning("PreZero has no container coordinates. Driving time uses their rule of 10 minutes between "
                       "containers; map positions are SYNTHETIC (illustrative). "
                       "stops, fill levels and overflow results do not.")


# ================================================================ 1 DATA
if page.startswith("1"):
    st.title("Data ingestion and quality")
    c = st.columns(4)
    c[0].metric("Readings", f"{qual['readings']:,}")
    c[1].metric("Sites / containers", f"{qual['sites']} / {qual['containers']}")
    c[2].metric("Period", f"{qual['date_min']} to {qual['date_max']}")
    c[3].metric("Median days between readings", f"{qual['gap_days_median']:.0f}")
    c = st.columns(4)
    c[0].metric("Mean fill at visit", f"{qual['mean_fill_at_visit']:.0f}%")
    c[1].metric("Readings at or over 100%", f"{qual['share_at_or_over_100'] * 100:.0f}%")
    c[2].metric("Readings at 50% or less", f"{qual['share_le_50'] * 100:.0f}%")
    c[3].metric("Readings at 90% or more", f"{qual['share_ge_90'] * 100:.0f}%")
    st.info("**What this says:** collection follows a schedule, not need. About 4 in 10 visits find a container at 50% or "
            "less, while about 1 in 3 finds it at 90% or more. Time since the last visit does not predict the fill level.")
    st.subheader("Assumptions of the model")
    st.markdown(
        "- **Confirmed by PreZero:** a reading is taken with the device **before** emptying.\n"
        "- **Confirmed by PreZero:** *overfull* means glass was lying next to the container. Readings of 100 / *overfull* "
        "are treated as **censored**: the true fill is at least 100%.\n"
        "- **From PreZero:** all containers are the same size (3 m3), a truck carries up to 12 t and takes all three colours, "
        "the shift is 8 hours, collection runs Monday to Friday, and enough trucks are available. Truck volume is unknown, "
        "so only the 12 t limit is used.\n"
        "- **From PreZero:** there are no coordinates; assume 10 minutes of driving between containers.\n"
        "- **Confirmed by PreZero:** every visit empties the container, and emptying one container takes about 5 minutes.\n"
        "- Still our own assumption: glass density (0.35 t/m3), which converts fill level into weight, and the unloading time.")
    st.subheader("Preview")
    st.dataframe(df.head(200), width="stretch", height=300)
    cov = df.groupby("container").size().describe().round(1).to_frame("readings per container")
    st.dataframe(cov.T, width="stretch")

# ============================================================ 2 PATTERNS
elif page.startswith("2"):
    st.title("Patterns")
    ms = monthly_summary(df)
    fig = go.Figure()
    fig.add_bar(x=ms["month"], y=ms["share_full_100"] * 100, name="visits at 100% or overfull")
    fig.add_bar(x=ms["month"], y=ms["share_below_40"] * 100, name="visits below 40%")
    fig.update_layout(barmode="group", yaxis_title="% of readings", title="Overflow and half-empty visits by month", height=380)
    st.plotly_chart(fig, width="stretch")
    c1, c2 = st.columns(2)
    with c1:
        ws = weekday_summary(df)
        st.plotly_chart(px.bar(ws, x="weekday", y="readings", title="Visits by weekday (collection is Monday to Friday)"),
                        width="stretch")
    with c2:
        mat = material_summary(df, iv)
        st.plotly_chart(px.bar(mat, x="material", y="mean_fill_pct", color="material", title="Mean fill at visit by glass type",
                               color_discrete_map={"white": "#bbbbbb", "green": "#3a8f3a", "brown": "#8b5a2b"}),
                        width="stretch")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Seasonality from the model")
        seas = model.seasonality_table()
        st.plotly_chart(px.bar(seas, x="month", y="multiplier", title="Fill-rate multiplier by month (1.0 = average)"),
                        width="stretch")
        st.caption(f"School-vacation effect after controlling for month and container: x{np.exp(model.g):.2f}. "
                   "The raw comparison below looks larger because vacations coincide with certain seasons.")
    with c2:
        st.subheader("Raw: vacation vs. school time")
        st.dataframe(calendar_effect(df, iv).round(2), width="stretch", hide_index=True)
    st.subheader("Container grouping: sites that behave alike")
    k = st.slider("Number of groups", 2, 6, 4)
    cl = _clusters(model, df, data_key, k)
    prof = cluster_profile(cl)
    c1, c2 = st.columns([1, 2])
    c1.dataframe(prof.round(2), hide_index=True, width="stretch")
    mats = [m for m in MATERIALS if m in cl.columns]
    if len(mats) >= 2:
        fig = px.scatter(cl, x=mats[0], y=mats[1], color="cluster", hover_data=["site"],
                         labels={mats[0]: f"{mats[0]} (log rate)", mats[1]: f"{mats[1]} (log rate)"},
                         title="Sites by log fill rate of two glass types")
        c2.plotly_chart(fig, width="stretch")
    st.download_button("Download site groups (CSV)", cl.to_csv(index=False), "site_groups.csv")

# ============================================================ 3 FORECAST
elif page.startswith("3"):
    st.title("Forecast")
    fm = _results("forecast_metrics.json")
    if fm:
        cv, fw = fm["cross_validation_mean"], fm["forward_test"]
        c = st.columns(4)
        c[0].metric("AUC 'needs collection (>=70%)' - model", f"{cv['AUC_need>=70_model']:.2f}")
        c[1].metric("same, using days since last visit", f"{cv['AUC_need>=70_days_since_last_visit']:.2f}",
                    help="What a fixed schedule effectively knows.")
        c[2].metric("Average error of predicted fill", f"{cv['MAE_model']:.1f} pp",
                    help=f"Material median: {cv['MAE_material_median']:.1f}; container median: {cv['MAE_container_median']:.1f}")
        c[3].metric("Forward test AUC (train to Mar)", f"{fw['AUC_need>=70_model']:.2f}",
                    help=f"Median baseline: {fw['AUC_need>=70_container_median']:.2f}")
    st.caption("Held-out readings, 5-fold cross-validation. AUC 1.0 = perfect, 0.5 = coin flip.")
    sites = sorted(df["site"].unique())
    c1, c2 = st.columns(2)
    site = c1.selectbox("Site", sites, index=0)
    mat = c2.selectbox("Glass type", [m for m in MATERIALS if f"{site}|{m}" in set(df["container"])])
    cont = f"{site}|{mat}"
    h = df[df["container"] == cont].sort_values("date")
    last = h["date"].max()
    horizon = st.slider("Days to forecast after the last reading", 14, 150, 90)
    tgt = pd.date_range(last, periods=horizon + 1, freq="D")
    n = len(tgt)
    cs, le = np.array([cont] * n), pd.DatetimeIndex([last] * n)
    pr = model.predict(cs, le, tgt, thresholds=(100,))
    q10, q90 = model.fill_quantile(cs, le, tgt, 0.1), model.fill_quantile(cs, le, tgt, 0.9)
    fig = go.Figure()
    fig.add_scatter(x=h["date"], y=h["fill"], mode="markers+lines", name="readings (at visits)", line=dict(width=1, color="#888"))
    fig.add_scatter(x=tgt, y=q90, mode="lines", line=dict(width=0), showlegend=False)
    fig.add_scatter(x=tgt, y=q10, mode="lines", fill="tonexty", line=dict(width=0), name="80% range",
                    fillcolor="rgba(30,120,200,0.2)")
    fig.add_scatter(x=tgt, y=pr["mean_fill"], mode="lines", name="expected fill if not emptied", line=dict(color="#1e78c8"))
    fig.add_hline(y=100, line_dash="dot", line_color="red")
    fig.update_layout(yaxis_title="fill %", yaxis_range=[0, 115], height=420,
                      title=f"{mat} container at site ...{site[-6:]}: reading history and forecast from the last visit")
    st.plotly_chart(fig, width="stretch")
    ttf = model.days_to_full([cont], [last], 0.5)[0]
    ttf_lo, ttf_hi = model.days_to_full([cont], [last], 0.9)[0], model.days_to_full([cont], [last], 0.1)[0]
    st.info(f"Median time to full: **{ttf:.0f} days** (80% range {ttf_lo:.0f} to {ttf_hi:.0f}). "
            f"Estimated fill rate {np.exp(model.a[model.cidx[cont]]) if cont in model.cidx else float('nan'):.1f}% per day.")

# ========================================================= 4 ROUTE PLANNER
elif page.startswith("4"):
    st.title("Route planner")
    with st.sidebar.expander("Operating variables", expanded=True):
        d = OpsConfig()
        cfg = OpsConfig(
            container_volume_m3=st.number_input("Container volume (m3)", 0.5, 10.0, d.container_volume_m3, 0.5),
            glass_density_t_m3=st.number_input("Glass density (t/m3)", 0.1, 1.5, d.glass_density_t_m3, 0.05),
            truck_volume_m3=st.number_input("Truck volume per trip (m3, 0 = no volume limit)", 0.0, 60.0, d.truck_volume_m3, 1.0),
            truck_payload_t=st.number_input("Truck payload per trip (t)", 2.0, 30.0, d.truck_payload_t, 0.5),
            max_vehicles=int(st.number_input("Max trucks", 1, 30, d.max_vehicles)),
            shift_hours=st.number_input("Shift length (h)", 4.0, 12.0, d.shift_hours, 0.5),
            fixed_travel_min=st.number_input("Minutes of driving between containers (0 = use coordinates)", 0.0, 60.0, d.fixed_travel_min, 1.0),
            avg_speed_kph=st.number_input("Average speed (km/h)", 10.0, 60.0, d.avg_speed_kph, 1.0),
            service_min_per_stop=st.number_input("Minutes per stop", 0.0, 20.0, d.service_min_per_stop, 0.5),
            service_min_per_bin=st.number_input("Minutes per container", 0.0, 20.0, d.service_min_per_bin, 0.5),
            unload_min=st.number_input("Unloading time at disposal (min)", 0.0, 60.0, d.unload_min, 1.0),
            vehicle_fixed_cost_min=st.number_input("Fleet-size priority (min per extra truck)", 0.0, 1000.0, d.vehicle_fixed_cost_min, 30.0),
            lookahead_days=int(st.number_input("Look-ahead (days)", 1, 7, d.lookahead_days)),
            must_p=st.slider("Overflow risk that makes a stop mandatory", 0.1, 0.95, d.must_p, 0.01),
        )
    st.caption("Container size, payload, shift, working days and the 10-minute driving rule come from PreZero. "
               "Glass density and unloading time are still our assumptions. "
               + ("Map positions are synthetic." if synthetic else "Using the uploaded site locations."))
    dmin, dmax = df["date"].min().date(), df["date"].max().date()
    default_day = pd.Timestamp("2026-08-17").date() if dmin < pd.Timestamp("2026-08-17").date() < dmax else dmax
    c1, c2 = st.columns([1, 2])
    plan_day = c1.date_input("Planning day", default_day, help="The planner only uses readings from BEFORE this day.")
    tl = c2.slider("Solver time (seconds)", 2, 30, 6)
    if pd.Timestamp(plan_day).dayofweek not in cfg.working_weekdays:
        st.warning("This is a Saturday or Sunday. PreZero collects Monday to Friday, so pick a weekday for a real plan.")
    known = df[df["date"] < pd.Timestamp(plan_day)]
    last_readings = known.groupby("container")["date"].max()
    state = df.drop_duplicates("container")[["container", "site", "material"]].copy()
    state["last_empty"] = state["container"].map(last_readings).fillna(df["date"].min())
    if pd.Timestamp(plan_day) > df["date"].max() + pd.Timedelta(days=7):
        st.warning("This day is well after the last reading. The planner assumes nothing was collected since, "
                   "so the backlog is huge. Pick a day inside the data period for a typical day.")
    bins = assess_bins(model, state, pd.Timestamp(plan_day), cfg)
    stops, take = select_stops(bins, locs, cfg)
    n_must, n_opt = int(stops["must"].sum()) if len(stops) else 0, int((~stops["must"]).sum()) if len(stops) else 0
    c = st.columns(4)
    c[0].metric("Containers likely overflowing within window", int((bins["p_over_window"] >= cfg.must_p).sum()))
    c[1].metric("Mandatory stops", n_must)
    c[2].metric("Optional stops considered", n_opt)
    c[3].metric("Sites in the network", df["site"].nunique())
    if stops.empty:
        st.success("Nothing needs collecting on this day with the current settings.")
    else:
        with st.spinner("Optimising routes ..."):
            plan = plan_routes(stops, cfg, time_limit_s=tl)
        k = plan.kpis
        c = st.columns(6)
        c[0].metric("Trucks needed", k["trucks"])
        c[1].metric("Trips (loads)", k["trips"])
        c[2].metric("Stops served", k["stops"])
        c[3].metric("Containers emptied", k["bins"])
        fixed = cfg.fixed_travel_min > 0
        c[4].metric("Distance", f"{k['km']:.0f} km" + (" *" if synthetic or fixed else ""))
        c[5].metric("Working hours (total)", f"{k['hours']:.1f} h" + (" *" if synthetic and not fixed else ""))
        if plan.dropped_mandatory:
            st.error(f"{len(plan.dropped_mandatory)} mandatory stops could not be scheduled (shift or truck limits). "
                     "Increase max trucks or shift length.")
        if plan.dropped_optional:
            st.caption(f"{len(plan.dropped_optional)} optional sites skipped because the detour was not worth it.")
        # map
        m = folium.Map(location=[cfg.depot_lat, cfg.depot_lon], zoom_start=12, tiles="OpenStreetMap")
        folium.Marker([cfg.depot_lat, cfg.depot_lon], tooltip="Depot (placeholder)", icon=folium.Icon(color="black", icon="home")).add_to(m)
        folium.Marker([cfg.disposal_lat, cfg.disposal_lon], tooltip="Disposal site (placeholder)", icon=folium.Icon(color="red", icon="trash")).add_to(m)
        palette = ["#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#008080", "#9a6324", "#800000"]
        fill_by_site = take.groupby("site")["fill_now"].mean()
        for r in plan.routes:
            col = palette[(r["truck"] - 1) % len(palette)]
            folium.PolyLine([(a, b) for a, b, _ in r["path"]], color=col, weight=3, opacity=0.8,
                            tooltip=f"Truck {r['truck']}: {r['km']:.0f} km, {r['hours']:.1f} h").add_to(m)
            for i, (s, la, lo) in enumerate(r["stops"], 1):
                folium.CircleMarker([la, lo], radius=6, color=col, fill=True, fill_opacity=0.9,
                                    tooltip=f"Truck {r['truck']} stop {i} - site ...{s[-6:]} ({fill_by_site.get(s, np.nan):.0f}% expected fill)").add_to(m)
        skipped = locs[locs["site"].isin(plan.dropped_optional)]
        for _, row in skipped.iterrows():
            folium.CircleMarker([row["lat"], row["lon"]], radius=4, color="#999", fill=True, tooltip="optional, skipped").add_to(m)
        st_folium(m, height=520, use_container_width=True, returned_objects=[])
        if cfg.fixed_travel_min > 0:
            st.caption(f"Working hours use PreZero's rule of {cfg.fixed_travel_min:.0f} minutes between containers. "
                       "* Kilometres are that driving time times the average speed. The map positions are synthetic, "
                       "so the map only shows which truck serves which stops.")
        elif synthetic:
            st.caption("* Positions are synthetic, so the map, kilometres and hours are illustrative.")
        # route table
        rows = []
        for r in plan.routes:
            for ti, t in enumerate(r["trips"], 1):
                rows.append({"truck": r["truck"], "trip": ti, "stops": len(t["stops"]),
                             "volume_m3": round(t["volume_m3"], 1), "weight_t": round(t["weight_t"], 1),
                             "site_sequence": " > ".join(s[-6:] for s in t["stops"])})
        trips_df = pd.DataFrame(rows)
        st.dataframe(trips_df, hide_index=True, width="stretch")
        st.download_button("Download route plan (CSV)", trips_df.to_csv(index=False), "route_plan.csv")
    with st.expander("Why these sites? (risk per container)"):
        st.dataframe(bins.sort_values("p_over_window", ascending=False).head(60).assign(
            fill_now=lambda x: x["fill_now"].round(0), p_over_window=lambda x: x["p_over_window"].round(2),
            p_over_now=lambda x: x["p_over_now"].round(2)), hide_index=True, width="stretch")

# ============================================================== 5 BACKTEST
elif page.startswith("5"):
    st.title("Backtest: fixed schedule vs. forecast-driven collection")
    fr, rs, meta = _results("frontier.csv"), _results("routed_summary.csv"), _results("meta.json")
    if fr is None or meta is None:
        st.warning("No results yet. Run `python run_backtest.py` once (about 10 minutes) and reload this page.")
    else:
        st.markdown(
            f"Replay of **{meta['start']} to {meta['end']}**. A simulated twin generates the true fill of every container; "
            "both policies are scored on the same random world. **Historical schedule** = the real visit calendar of the data. "
            "**Dynamic** = each weekday, containers likely to overflow are selected from the forecast and routed. "
            "The planner only knows when a container was last emptied (no live sensors).")
        base = fr[fr["policy"] == "historical schedule"].iloc[0]
        dyn = fr[fr["policy"].str.startswith("dynamic")]
        fig = px.line(dyn.sort_values("site_visits"), x="site_visits", y="overflow_bin_days", color="policy", markers=True,
                      hover_data=["threshold", "mean_fill_at_collection_pct"],
                      labels={"site_visits": "site visits in the period", "overflow_bin_days": "container-days spent full (overflow)"},
                      title="Efficiency frontier: lower left is better")
        fig.add_scatter(x=[base["site_visits"]], y=[base["overflow_bin_days"]], mode="markers",
                        marker=dict(size=14, color="black", symbol="diamond"), name="historical schedule")
        st.plotly_chart(fig, width="stretch")
        if rs is not None:
            st.subheader("Routed comparison (including distance and working time)")
            show = rs.set_index("name")[["site_visits", "bin_collections", "mean_fill_at_collection_pct",
                                         "share_collections_below_40pct", "overflow_bin_days", "overflow_events",
                                         "km", "hours", "truck_days"]].copy()
            show["mean_fill_at_collection_pct"] = show["mean_fill_at_collection_pct"].round(1)
            show["share_collections_below_40pct"] = (show["share_collections_below_40pct"] * 100).round(0)
            show[["km", "hours"]] = show[["km", "hours"]].round(0)
            st.dataframe(show.T, width="stretch")
            if "baseline_replay" in rs["name"].values:
                b = rs[rs["name"] == "baseline_replay"].iloc[0]
                for nme in ("dynamic_same_service", "dynamic_same_effort"):
                    if nme in rs["name"].values:
                        r = rs[rs["name"] == nme].iloc[0]
                        st.markdown(
                            f"**{nme.replace('_', ' ')}**: site visits {100 * (r['site_visits'] / b['site_visits'] - 1):+.0f}%, "
                            f"overflow-days {100 * (r['overflow_bin_days'] / b['overflow_bin_days'] - 1):+.0f}%, "
                            f"working hours {100 * (r['hours'] / b['hours'] - 1):+.0f}%, truck-days {100 * (r['truck_days'] / b['truck_days'] - 1):+.0f}%.")
        st.warning("**Read with care.** The twin shares its structure with the forecast model, and the data only has readings at visits, "
                   "so absolute numbers are indicative. Dynamic collection reduces the *time* containers sit full and the number of "
                   "wasted half-empty visits; it does not remove overflow events entirely, because individual filling cycles are "
                   "unpredictable without live sensors. Working time uses PreZero's rule of 10 minutes between containers.")

# ================================================================== 6 GUIDE
else:
    st.title("Guide: architecture and how to use")
    st.markdown(open(os.path.join(HERE, "README.md")).read())
