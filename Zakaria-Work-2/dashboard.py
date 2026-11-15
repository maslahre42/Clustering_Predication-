"""
WasteRouting.AI — Executive Optimization Dashboard
PreZero Smart Waste & City of Heilbronn
Operations Research Fleet Optimization Engine & Executive Decision Support
"""

import os
import sys
import json
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import folium
import altair as alt

# Ensure root directory is on sys.path
root_dir = os.path.abspath(os.path.dirname(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Page configuration
st.set_page_config(
    page_title="WasteRouting.AI | PreZero & City of Heilbronn",
    page_icon="♻️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------------------------------------------------------
# CUSTOM CSS: PREZERO BRAND PALETTE & SLEEK GLASSMORPHISM
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600;700&display=swap');

    :root {
        --prezero-green: #00d26a;
        --prezero-green-glow: rgba(0, 210, 106, 0.4);
        --bg-midnight: #0a0f1d;
        --bg-navy-dark: #0d1527;
        --bg-card: rgba(17, 26, 46, 0.85);
        --card-border: rgba(255, 255, 255, 0.08);
        --text-main: #f8fafc;
        --text-muted: #94a3b8;
    }

    /* Overall Background */
    .stApp {
        background-color: #0a0f1d;
        background-image: 
            radial-gradient(circle at 10% 10%, rgba(0, 210, 106, 0.06) 0%, transparent 40%),
            radial-gradient(circle at 90% 80%, rgba(0, 229, 255, 0.05) 0%, transparent 40%);
        font-family: 'Inter', sans-serif;
        color: #f8fafc;
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #0d1527 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.08);
    }

    /* Hero KPI Cards */
    .hero-card {
        background: rgba(17, 26, 46, 0.85);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 18px 20px;
        position: relative;
        overflow: hidden;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .hero-card:hover {
        transform: translateY(-2px);
        border-color: rgba(0, 210, 106, 0.4);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
    }
    .hero-title {
        font-size: 0.78rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94a3b8;
        margin-bottom: 8px;
    }
    .hero-val {
        font-size: 1.85rem;
        font-weight: 800;
        font-family: 'JetBrains Mono', monospace;
        color: #ffffff;
        letter-spacing: -0.02em;
    }
    .hero-badge {
        display: inline-block;
        font-size: 0.75rem;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
        padding: 3px 8px;
        border-radius: 6px;
        background: rgba(0, 210, 106, 0.15);
        color: #52f099;
        border: 1px solid rgba(0, 210, 106, 0.3);
        margin-left: 8px;
    }
    .hero-badge.amber {
        background: rgba(245, 158, 11, 0.15);
        color: #fcd34d;
        border-color: rgba(245, 158, 11, 0.3);
    }
    .hero-badge.cyan {
        background: rgba(0, 229, 255, 0.15);
        color: #00e5ff;
        border-color: rgba(0, 229, 255, 0.3);
    }
    .hero-sub {
        font-size: 0.78rem;
        color: #64748b;
        margin-top: 6px;
        line-height: 1.4;
    }

    /* Badges */
    .badge-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.74rem;
        font-weight: 600;
        font-family: 'JetBrains Mono', monospace;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        color: #94a3b8;
    }
    .badge-pill.active {
        background: rgba(0, 210, 106, 0.1);
        border-color: rgba(0, 210, 106, 0.4);
        color: #ffffff;
    }
    .pulse-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #00d26a;
        box-shadow: 0 0 10px #00d26a;
    }

    /* Glass Container */
    .glass-box {
        background: rgba(17, 26, 46, 0.85);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 20px;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# DATA LOADING & CACHING
# -----------------------------------------------------------------------------
@st.cache_data
def load_all_dashboard_data():
    json_path = os.path.join("data", "dashboard_data.json")
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data

    # Fallback to generating data if json doesn't exist
    from src.generate_dashboard_data import build_dashboard_data
    build_dashboard_data()
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


data = load_all_dashboard_data()
kpis = data["kpis"]
depots = data["depots"]
truck_routes = data["truck_routes"]
stations = data["stations"]
exp_a = data["experiment_a"]
exp_b = data["experiment_b"]


# -----------------------------------------------------------------------------
# SIDEBAR NAVIGATION & STATUS
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("""
    <div style="display:flex; align-items:center; gap:12px; margin-bottom:16px;">
        <div style="width:38px; height:38px; border-radius:10px; background:linear-gradient(135deg, #00d26a, #008744); display:flex; align-items:center; justify-content:center; box-shadow:0 0 15px rgba(0,210,106,0.4);">
            <span style="font-size:20px;">♻️</span>
        </div>
        <div>
            <div style="font-size:1.05rem; font-weight:800; color:#fff; letter-spacing:-0.02em;">WasteRouting.AI</div>
            <div style="font-size:0.75rem; color:#94a3b8;">PreZero & Heilbronn</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    nav_choice = st.radio(
        "Navigation",
        [
            "Executive Overview",
            "Interactive GIS Map",
            "Dual Benchmarks (Exp A & B)",
            "Container Fleet Telemetry",
            "Live Scenario Simulator",
            "OR Formulation & Engine"
        ],
        index=0
    )

    st.markdown("---")
    st.markdown("<div style='font-size:0.75rem; text-transform:uppercase; color:#94a3b8; font-weight:700; margin-bottom:8px;'>System Audit Status</div>", unsafe_allow_html=True)
    
    st.markdown("""
    <div style="display:flex; flex-direction:column; gap:8px;">
        <div class="badge-pill active">
            <span class="pulse-dot"></span>
            Gurobi MILP Engine: v14.0
        </div>
        <div class="badge-pill active">
            <span class="pulse-dot"></span>
            OSRM Asymmetric Graph (111 Nodes)
        </div>
        <div class="badge-pill active">
            <span class="pulse-dot"></span>
            MTVRP Multi-Trip Dispatch
        </div>
        <div class="badge-pill">
            Zero-Overflow Guarantee: 100%
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("<div style='font-size:0.72rem; color:#64748b;'>Hackathon 2026 &bull; City of Heilbronn &bull; PreZero Dual-Experiment Benchmark</div>", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# TOP EXECUTIVE HEADER
# -----------------------------------------------------------------------------
st.markdown("""
<div style="display:flex; justify-content:space-between; align-items:flex-end; margin-bottom:20px;">
    <div>
        <h1 style="font-size:1.8rem; font-weight:800; color:#ffffff; margin:0; letter-spacing:-0.03em;">
            PreZero Smart Waste &bull; Executive Decision Dashboard
        </h1>
        <p style="font-size:0.85rem; color:#94a3b8; margin-top:4px;">
            Operations Research Engine: Demand-Responsive Glass Container Collection & Dynamic Dispatch Optimization
        </p>
    </div>
    <div style="text-align:right;">
        <span class="badge-pill active" style="font-size:0.78rem;">Shift: 06:00 - 14:00 (8h)</span>
    </div>
</div>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# EXECUTIVE HERO KPI BAR (Rendered on all pages or prominently)
# -----------------------------------------------------------------------------
kpi_cols = st.columns(5)

with kpi_cols[0]:
    st.markdown(f"""
    <div class="hero-card">
        <div class="hero-title">Daily Cost Savings</div>
        <div>
            <span class="hero-val">€{kpis['cost_savings_daily_prorata']:,.2f}</span>
            <span class="hero-badge">-{kpis['cost_savings_daily_prorata_pct']}%</span>
        </div>
        <div class="hero-sub">
            <b>€{kpis['annual_cost_savings_prorata']:,.0f}/yr</b> shift savings. €4,000/day saved under vehicle charter.
        </div>
    </div>
    """, unsafe_allow_html=True)

with kpi_cols[1]:
    st.markdown(f"""
    <div class="hero-card">
        <div class="hero-title">Distance Reduction</div>
        <div>
            <span class="hero-val">-{kpis['distance_reduction_exp_b_pct']}%</span>
            <span class="hero-badge cyan">-311.5 km</span>
        </div>
        <div class="hero-sub">
            Down from 398.6 km to <b>87.0 km</b> today. Pure routing saves <b>-45.7%</b> on identical bins.
        </div>
    </div>
    """, unsafe_allow_html=True)

with kpi_cols[2]:
    st.markdown(f"""
    <div class="hero-card">
        <div class="hero-title">Tailpipe CO2 Abated</div>
        <div>
            <span class="hero-val">-78.2%</span>
            <span class="hero-badge">-264.8 kg</span>
        </div>
        <div class="hero-sub">
            <b>{kpis['annual_co2_saved_tonnes']} tonnes CO2/yr</b> avoided (EF = 0.85 kg/km). 24,900 L fuel saved.
        </div>
    </div>
    """, unsafe_allow_html=True)

with kpi_cols[3]:
    st.markdown(f"""
    <div class="hero-card">
        <div class="hero-title">Zero Overflows</div>
        <div>
            <span class="hero-val">100%</span>
            <span class="hero-badge amber">0 Overflows</span>
        </div>
        <div class="hero-sub">
            All 20 critical bins (&ge;100%) serviced. <b>25 premature collections (&lt;40%) eliminated</b>.
        </div>
    </div>
    """, unsafe_allow_html=True)

with kpi_cols[4]:
    st.markdown(f"""
    <div class="hero-card">
        <div class="hero-title">Collection Yield</div>
        <div>
            <span class="hero-val">272.0</span>
            <span class="hero-badge" style="background:rgba(168,85,247,0.15); color:#c084fc; border-color:rgba(168,85,247,0.3);">+{kpis['collection_yield_gain_pct']}% kg/km</span>
        </div>
        <div class="hero-sub">
            Up from 178.7 kg/km in calendar sweep. Yield reaches <b>+182.6%</b> over low-fill routes.
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# PAGE 1: EXECUTIVE OVERVIEW
# -----------------------------------------------------------------------------
if nav_choice == "Executive Overview":
    st.subheader("Executive Operations Summary")

    row1_c1, row1_c2 = st.columns([1.3, 1])

    with row1_c1:
        st.markdown("""
        <div class="glass-box">
            <h3 style="color:#ffffff; font-size:1.15rem; margin-bottom:8px;">Transformation: Static Sweep &rarr; Dynamic Gurobi Dispatch</h3>
            <p style="font-size:0.85rem; color:#94a3b8; line-height:1.6;">
                The City of Heilbronn operates 109 municipal glass recycling stations. Historically, collection vehicles sweep all 109 containers on fixed weekly calendar cycles regardless of fill levels, causing <b>25 premature collections of half-empty bins (&lt;40%)</b> and risking chronic street overflows at high-volume stations.
            </p>
            <p style="font-size:0.85rem; color:#94a3b8; line-height:1.6; margin-top:8px;">
                Our <b>WasteRouting.AI</b> operations research pipeline integrates IoT sensor fill forecasting, K-Means behavioral clustering (4 tiers), and a Gurobi Mixed-Integer Linear Programming (MILP) CVRP solver over asymmetric OSRM road networks:
            </p>
            <ul style="font-size:0.82rem; color:#cbd5e1; margin-top:8px; padding-left:20px; line-height:1.6;">
                <li><b>Prioritizes 24 high-fill candidates</b> (20 urgent &ge;80% + 4 opportunistic 60-80% near route corridors).</li>
                <li><b>Safely defers 85 bins</b> with mean fill 58.9%, maintaining zero immediate overflow risk.</li>
                <li><b>Slices road distance by 78.2%</b> (from 398.6 km to 87.0 km today), saving <b>€1,289.11 / day</b>.</li>
                <li><b>MTVRP Multi-Trip Feasibility</b>: All 4 vehicle collection trips finish in <b>6.45 hours total</b> (including 20-min intermediate unloadings at Böllinger Höfe), fitting within <b>1 single 8-hour truck shift</b>.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    with row1_c2:
        st.markdown("""
        <div class="glass-box">
            <h3 style="color:#ffffff; font-size:1.15rem; margin-bottom:12px;">Fleet Resource Allocation</h3>
        """, unsafe_allow_html=True)

        fleet_df = pd.DataFrame([
            {"Metric": "Truck #1", "Stops": 7, "Distance": "22.69 km", "Volume": "17.24 m³ (95.8%)", "Shift": "1.77 h"},
            {"Metric": "Truck #2", "Stops": 5, "Distance": "12.77 km", "Volume": "12.88 m³ (71.6%)", "Shift": "1.29 h"},
            {"Metric": "Truck #3", "Stops": 6, "Distance": "33.68 km", "Volume": "15.69 m³ (87.2%)", "Shift": "1.83 h"},
            {"Metric": "Truck #4", "Stops": 6, "Distance": "17.90 km", "Volume": "16.50 m³ (91.7%)", "Shift": "1.56 h"},
            {"Metric": "Total / Fleet", "Stops": 24, "Distance": "87.04 km", "Volume": "62.31 m³ (23.7 t)", "Shift": "6.45 h"}
        ])
        st.dataframe(fleet_df, hide_index=True, use_container_width=True)

        st.markdown("""
            <div style="font-size:0.75rem; color:#94a3b8; margin-top:8px;">
                Depot: Central Yard (Node 0) &bull; Intermediate Disposal: Böllinger Höfe (Node N+1)
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Mini GIS Map Preview
    st.subheader("Live Operational Map Preview")
    m = folium.Map(location=[49.145, 9.215], zoom_start=13, tiles="OpenStreetMap")
    folium.Marker(
        [depots["central_yard"]["lat"], depots["central_yard"]["lng"]],
        tooltip="Central Yard (Depot 0)",
        icon=folium.Icon(color="black", icon="home")
    ).add_to(m)
    folium.Marker(
        [depots["disposal_facility"]["lat"], depots["disposal_facility"]["lng"]],
        tooltip="Disposal Facility (Böllinger Höfe)",
        icon=folium.Icon(color="red", icon="trash")
    ).add_to(m)

    for truck in truck_routes:
        if truck.get("coordinates"):
            folium.PolyLine(
                truck["coordinates"],
                color=truck["color"],
                weight=4,
                opacity=0.85,
                tooltip=f"{truck['vehicle']}: {truck['num_stops']} stops, {truck['total_distance_km']} km"
            ).add_to(m)

    for st_rec in stations[:35]:
        col = "#ef4444" if st_rec["predicted_fill_perc"] >= 80 else ("#f59e0b" if st_rec["predicted_fill_perc"] >= 60 else "#3b82f6")
        folium.CircleMarker(
            [st_rec["latitude"], st_rec["longitude"]],
            radius=6 if st_rec["assigned_truck"] else 4,
            color="#ffffff" if st_rec["assigned_truck"] else col,
            weight=1.5,
            fill=True,
            fill_color=col,
            fill_opacity=0.85,
            tooltip=f"POI #{st_rec['poi_id']}: {st_rec['street_name']} ({st_rec['predicted_fill_perc']}%)"
        ).add_to(m)

    components.html(m._repr_html_(), height=420)


# -----------------------------------------------------------------------------
# PAGE 2: INTERACTIVE GIS MAP & ROUTE NETWORK
# -----------------------------------------------------------------------------
elif nav_choice == "Interactive GIS Map":
    st.subheader("Heilbronn Smart Glass Collection GIS Network")
    st.markdown("Interactive GIS map with turn-by-turn road network routes, container stations, and intermediate disposal turnaround.")

    col_filter1, col_filter2 = st.columns([1, 1])
    with col_filter1:
        map_filter = st.selectbox(
            "Station Filter Layer",
            ["All 109 Stations", "Dispatched Bins (24)", "Urgent (>=80%)", "Opportunistic (60-80%)", "Deferred Safe (<60%)"]
        )
    with col_filter2:
        selected_trucks = st.multiselect(
            "Active Vehicle Routes to Display",
            ["Truck #1", "Truck #2", "Truck #3", "Truck #4"],
            default=["Truck #1", "Truck #2", "Truck #3", "Truck #4"]
        )

    # Build Map
    gis_map = folium.Map(location=[49.145, 9.215], zoom_start=13, tiles="OpenStreetMap")

    # Central Yard (Depot 0)
    folium.Marker(
        [depots["central_yard"]["lat"], depots["central_yard"]["lng"]],
        tooltip="<b>Central Yard (Depot 0)</b><br>Fleet Departure & Final Terminal Depot",
        icon=folium.Icon(color="black", icon="home")
    ).add_to(gis_map)

    # Disposal Depot (Böllinger Höfe)
    folium.Marker(
        [depots["disposal_facility"]["lat"], depots["disposal_facility"]["lng"]],
        tooltip="<b>Entsorgungszentrum Böllinger Höfe (Node N+1)</b><br>Unloading Turnaround Site (20 min)",
        icon=folium.Icon(color="red", icon="trash")
    ).add_to(gis_map)

    # Render Routes
    for truck in truck_routes:
        if truck["vehicle"] in selected_trucks and truck.get("coordinates"):
            folium.PolyLine(
                truck["coordinates"],
                color=truck["color"],
                weight=4.5,
                opacity=0.88,
                tooltip=f"<b>{truck['vehicle']}</b>: {truck['num_stops']} stops | {truck['total_distance_km']} km | {truck['shift_hours']} hrs | {truck['total_weight_kg']} kg"
            ).add_to(gis_map)

    # Render Markers
    for st_rec in stations:
        pred_fill = st_rec["predicted_fill_perc"]
        is_disp = st_rec["assigned_truck"] is not None

        # Filter check
        if map_filter == "Dispatched Bins (24)" and not is_disp:
            continue
        elif map_filter == "Urgent (>=80%)" and pred_fill < 80.0:
            continue
        elif map_filter == "Opportunistic (60-80%)" and (pred_fill < 60.0 or pred_fill >= 80.0):
            continue
        elif map_filter == "Deferred Safe (<60%)" and pred_fill >= 60.0:
            continue

        marker_col = "#ef4444" if pred_fill >= 80 else ("#f59e0b" if pred_fill >= 60 else "#3b82f6")
        
        popup_html = f"""
        <div style="font-family:'Inter', sans-serif; font-size:12px; width:220px;">
            <b style="font-size:13px;">POI #{st_rec['poi_id']}</b><br>
            <i>{st_rec['street_name']}</i><br><br>
            <b>Predicted Fill:</b> <span style="color:{marker_col}; font-weight:700;">{pred_fill}%</span><br>
            <b>Velocity:</b> +{st_rec['daily_velocity']}% / day<br>
            <b>Mix:</b> W: {st_rec['white_glass_fill']}% | G: {st_rec['green_glass_fill']}% | B: {st_rec['brown_glass_fill']}%<br>
            <b>Status:</b> {st_rec['next_service']}
        </div>
        """

        folium.CircleMarker(
            [st_rec["latitude"], st_rec["longitude"]],
            radius=7.5 if is_disp else 5,
            color="#ffffff" if is_disp else "rgba(255,255,255,0.4)",
            weight=2 if is_disp else 1,
            fill=True,
            fill_color=marker_col,
            fill_opacity=0.9,
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=f"POI #{st_rec['poi_id']}: {st_rec['street_name']} ({pred_fill}%)"
        ).add_to(gis_map)

    components.html(gis_map._repr_html_(), height=600)


# -----------------------------------------------------------------------------
# PAGE 3: DUAL BENCHMARKS (EXPERIMENT A & B)
# -----------------------------------------------------------------------------
elif nav_choice == "Dual Benchmarks (Exp A & B)":
    st.subheader("Audited Optimization Benchmarks & Scientific Controls")
    st.markdown("Dual-experiment methodology separating pure mathematical routing efficiency from macro-level municipal policy savings.")

    benchmark_tab = st.radio(
        "Select Benchmark Experiment",
        ["Experiment A: Pure Routing Efficiency (Identical 24 Containers)",
         "Experiment B: Dynamic AI Dispatch vs. Fixed Sweep (Full 109 Containers)"],
        horizontal=True
    )

    if "Experiment A" in benchmark_tab:
        st.markdown("""
        <div class="glass-box">
            <h4 style="color:#ffffff; margin-bottom:6px;">Experiment A: Scientific Control on Identical 24 Containers</h4>
            <p style="font-size:0.82rem; color:#94a3b8;">
                <b>Scientific Control:</b> The input set of 24 containers, container demands, depot (Node 0), disposal facility (Node N+1), and truck capacities are <b>100% identical</b> across all three solvers.
            </p>
        </div>
        """, unsafe_allow_html=True)

        exp_a_df = pd.DataFrame(exp_a["metrics"])
        st.dataframe(exp_a_df, hide_index=True, use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            chart_data_a = pd.DataFrame({
                "Engine": ["Fixed Municipal Order", "Greedy Nearest-Neighbor", "Gurobi Optimal CVRP"],
                "Distance (km)": [160.39, 90.68, 87.04]
            })
            chart_a1 = alt.Chart(chart_data_a).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
                x=alt.X("Engine:N", sort=None, title="Routing Solver"),
                y=alt.Y("Distance (km):Q", title="Road Distance (km)"),
                color=alt.Color("Engine:N", scale=alt.Scale(range=["#ef4444", "#f59e0b", "#00d26a"]), legend=None)
            ).properties(height=260, title="Pure Road Distance Comparison (km)")
            st.altair_chart(chart_a1, use_container_width=True)

        with c2:
            chart_data_cost = pd.DataFrame({
                "Engine": ["Fixed Municipal Order", "Greedy Nearest-Neighbor", "Gurobi Optimal CVRP"],
                "Operating Cost (€)": [529.62, 407.09, 403.13]
            })
            chart_a2 = alt.Chart(chart_data_cost).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
                x=alt.X("Engine:N", sort=None, title="Routing Solver"),
                y=alt.Y("Operating Cost (€):Q", title="Shift Cost (€ @ 62.50 €/h)"),
                color=alt.Color("Engine:N", scale=alt.Scale(range=["#ef4444", "#f59e0b", "#00d26a"]), legend=None)
            ).properties(height=260, title="Shift Operating Cost (€)")
            st.altair_chart(chart_a2, use_container_width=True)

    else:
        st.markdown("""
        <div class="glass-box">
            <h4 style="color:#ffffff; margin-bottom:6px;">Experiment B: Municipal Macro Policy Comparison (Full 109 Containers)</h4>
            <p style="font-size:0.82rem; color:#94a3b8;">
                <b>Strategic Policy Shift:</b> Transitioning the entire municipal sector from static calendar-based sweeping to predictive demand-responsive collection.
            </p>
        </div>
        """, unsafe_allow_html=True)

        exp_b_df = pd.DataFrame(exp_b["metrics"])
        st.dataframe(exp_b_df, hide_index=True, use_container_width=True)

        # Deferred Containers Audit Panel
        st.markdown("""
        <div class="glass-box" style="border-color:rgba(0,210,106,0.3); background:rgba(0,210,106,0.05);">
            <h4 style="color:#52f099; margin-bottom:8px;">Deferred Containers Tracking Audit (Zero Overflow Integrity)</h4>
            <p style="font-size:0.82rem; color:#cbd5e1;">
                85 non-critical containers were deferred to future collection cycles. Sensor audit confirms:
            </p>
            <div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:12px; margin-top:10px;">
                <div style="background:rgba(10,15,29,0.7); padding:10px 14px; border-radius:8px;">
                    <div style="font-size:0.72rem; color:#94a3b8;">BINS DEFERRED</div>
                    <div style="font-size:1.1rem; font-weight:700; color:#00d26a;">85 / 109 (78.0%)</div>
                </div>
                <div style="background:rgba(10,15,29,0.7); padding:10px 14px; border-radius:8px;">
                    <div style="font-size:0.72rem; color:#94a3b8;">MEAN PREDICTED FILL</div>
                    <div style="font-size:1.1rem; font-weight:700; color:#00e5ff;">58.9% (Safe)</div>
                </div>
                <div style="background:rgba(10,15,29,0.7); padding:10px 14px; border-radius:8px;">
                    <div style="font-size:0.72rem; color:#94a3b8;">PREMATURE TRIPS SAVED</div>
                    <div style="font-size:1.1rem; font-weight:700; color:#f59e0b;">25 Stops Eliminated</div>
                </div>
                <div style="background:rgba(10,15,29,0.7); padding:10px 14px; border-radius:8px;">
                    <div style="font-size:0.72rem; color:#94a3b8;">OVERFLOW RISK</div>
                    <div style="font-size:1.1rem; font-weight:700; color:#52f099;">0 Bins at Risk</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# PAGE 4: CONTAINER FLEET TELEMETRY & INSPECTOR
# -----------------------------------------------------------------------------
elif nav_choice == "Container Fleet Telemetry":
    st.subheader("Container Fleet Telemetry & Station Inspector")
    st.markdown("Granular sensor telemetry, fill velocity, glass color mix, and dynamic collection dispatch status.")

    tf_col1, tf_col2, tf_col3 = st.columns([1.5, 1, 1])
    with tf_col1:
        search_kw = st.text_input("🔍 Search Street Name or Station POI ID", "")
    with tf_col2:
        urgency_filter = st.selectbox(
            "Filter Urgency Level",
            ["All", "Dispatched Today (24)", "Urgent (>=80%)", "Opportunistic (60-79%)", "Deferred / Safe (<60%)"]
        )
    with tf_col3:
        tier_filter = st.selectbox(
            "Filter Cluster Tier",
            ["All", "Tier 1: Critical High-Volume", "Tier 2: Steady High-Demand", "Tier 3: Moderate Regular", "Tier 4: Low-Demand / Sporadic"]
        )

    # Filter stations
    filtered = []
    for s in stations:
        if search_kw:
            kw = search_kw.lower()
            if kw not in s["poi_id"].lower() and kw not in s["street_name"].lower():
                continue
        if urgency_filter == "Dispatched Today (24)" and s["assigned_truck"] is None:
            continue
        elif urgency_filter != "All" and urgency_filter != "Dispatched Today (24)" and s["urgency_status"] != urgency_filter:
            continue
        if tier_filter != "All" and tier_filter not in s["tier"]:
            continue
        filtered.append(s)

    telemetry_table_data = []
    for s in filtered:
        telemetry_table_data.append({
            "POI ID": s["poi_id"],
            "Street Name": s["street_name"],
            "Cluster Tier": s["tier"].split(":")[0],
            "Predicted Fill (%)": f"{s['predicted_fill_perc']}%",
            "White Glass": f"{s['white_glass_fill']}%",
            "Green Glass": f"{s['green_glass_fill']}%",
            "Brown Glass": f"{s['brown_glass_fill']}%",
            "Velocity (%/day)": f"+{s['daily_velocity']}%",
            "Days Idle": f"{s['days_since_collection']} d",
            "Service Window": s["next_service"]
        })

    st.dataframe(pd.DataFrame(telemetry_table_data), use_container_width=True, height=450)

    # Station Inspector Dropdown
    st.markdown("---")
    st.subheader("Station Inspector Diagnostic")
    selected_poi = st.selectbox("Select Station to Inspect", [s["poi_id"] + " - " + s["street_name"] for s in stations])
    poi_id = selected_poi.split(" - ")[0]
    st_rec = next((s for s in stations if s["poi_id"] == poi_id), None)

    if st_rec:
        sc1, sc2, sc3, sc4 = st.columns(4)
        with sc1:
            st.metric("Predicted Fill Level", f"{st_rec['predicted_fill_perc']}%", f"+{st_rec['daily_velocity']}% / day")
        with sc2:
            st.metric("Estimated Glass Weight", f"{st_rec['demand_weight_kg']} kg", f"{st_rec['demand_volume_m3']} m³")
        with sc3:
            st.metric("Cluster Classification", st_rec['tier'].split(':')[0], st_rec['tier'].split(':')[1] if ':' in st_rec['tier'] else "")
        with sc4:
            st.metric("Dispatch Assignment", st_rec['assigned_truck'] if st_rec['assigned_truck'] else "Deferred", st_rec['next_service'])


# -----------------------------------------------------------------------------
# PAGE 5: LIVE SCENARIO SIMULATOR & COST CALCULATOR
# -----------------------------------------------------------------------------
elif nav_choice == "Live Scenario Simulator":
    st.subheader("Interactive Operational Scenario Simulator & Cost Calculator")
    st.markdown("Test fleet parameters, shift lengths, diesel prices, and fill thresholds to assess municipal budget impact.")

    sim_c1, sim_c2 = st.columns([1.1, 1])

    with sim_c1:
        st.markdown("<div class='glass-box'>", unsafe_allow_html=True)
        st.markdown("#### Input Operational Parameters")

        truck_cost = st.slider("Truck Daily Operating Cost (€/8h shift)", 300.0, 900.0, 500.0, 25.0)
        shift_hours = st.slider("Max Driver Shift Duration (hours)", 6.0, 10.0, 8.0, 0.5)
        diesel_price = st.slider("Diesel Fuel Price (€/Liter)", 1.30, 2.40, 1.75, 0.05)
        urgency_thresh = st.slider("Urgency Collection Threshold (%)", 65.0, 90.0, 80.0, 5.0)
        op_days = st.slider("Annual Operating Days", 200, 300, 250, 10)
        st.markdown("</div>", unsafe_allow_html=True)

    with sim_c2:
        # Dynamic Reactive Computations
        hourly_rate = truck_cost / shift_hours
        baseline_shift_hours = 27.08
        dynamic_shift_hours = 6.45
        saved_hours_daily = baseline_shift_hours - dynamic_shift_hours # 20.63h

        daily_prorata_savings = saved_hours_daily * hourly_rate
        annual_prorata_savings = daily_prorata_savings * op_days

        baseline_km = 398.6
        dynamic_km = 87.0
        saved_km_daily = baseline_km - dynamic_km # 311.6 km
        daily_fuel_liters = saved_km_daily * 0.32
        annual_fuel_liters = daily_fuel_liters * op_days
        annual_fuel_cost = annual_fuel_liters * diesel_price

        daily_co2_kg = saved_km_daily * 0.85
        annual_co2_tonnes = (daily_co2_kg * op_days) / 1000.0

        st.markdown(f"""
        <div class="glass-box" style="border-color:rgba(0,210,106,0.3); background:rgba(17,26,46,0.95);">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <h3 style="color:#ffffff; margin:0;">Simulated Annual Impact</h3>
                <span class="badge-pill active">€{hourly_rate:.2f} / hr</span>
            </div>
            <div style="margin-top:16px;">
                <div style="font-size:0.75rem; text-transform:uppercase; color:#94a3b8;">Projected Annual Shift Savings</div>
                <div style="font-size:2.2rem; font-weight:800; color:#52f099; font-family:'JetBrains Mono';">€{annual_prorata_savings:,.0f}</div>
                <div style="font-size:0.8rem; color:#cbd5e1; margin-top:2px;">
                    Daily shift savings: <b>€{daily_prorata_savings:,.2f} / day</b>
                </div>
            </div>
            <div style="margin-top:16px;">
                <div style="font-size:0.75rem; text-transform:uppercase; color:#94a3b8;">Annual Carbon Abated</div>
                <div style="font-size:1.8rem; font-weight:800; color:#00e5ff; font-family:'JetBrains Mono';">{annual_co2_tonnes:.1f} Tonnes CO2</div>
                <div style="font-size:0.8rem; color:#cbd5e1; margin-top:2px;">
                    Diesel saved: <b>{annual_fuel_liters:,.0f} Liters/yr</b> (<b>€{annual_fuel_cost:,.0f}/yr</b>)
                </div>
            </div>
            <div style="margin-top:16px; padding:12px; border-radius:8px; background:rgba(0,210,106,0.08); border:1px solid rgba(0,210,106,0.2);">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <b style="color:#52f099; font-size:0.85rem;">MTVRP 1-Truck Shift Feasibility</b>
                    <span class="badge-pill active">{'FEASIBLE' if dynamic_shift_hours <= shift_hours else 'REQUIRES 2 TRUCKS'}</span>
                </div>
                <div style="font-size:0.78rem; color:#cbd5e1; margin-top:4px;">
                    {dynamic_shift_hours:.2f}h required &le; {shift_hours:.1f}h shift limit. 1 physical truck handles all 4 trips sequentially.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# PAGE 6: OPERATIONS RESEARCH FORMULATION & ENGINE
# -----------------------------------------------------------------------------
elif nav_choice == "OR Formulation & Engine":
    st.subheader("Operations Research Engine & Mathematical Formulation")
    st.markdown("Detailed mathematical formulation of the Gurobi Capacitated Vehicle Routing Problem (CVRP) with MTVRP and MTZ subtour elimination.")

    f_col1, f_col2 = st.columns(2)

    with f_col1:
        st.markdown("""
        <div class="glass-box">
            <h4 style="color:#00d26a;">1. Mathematical CVRP Formulation</h4>
            <p style="font-size:0.82rem; color:#94a3b8; line-height:1.5;">
                Let <i>V = {0, 1, ..., N, N+1}</i> denote network nodes where Node 0 is the Central Yard and Node N+1 is the Disposal Facility at Böllinger Höfe.<br><br>
                <b>Decision Variables:</b><br>
                &bull; <i>x<sub>ijk</sub> &isin; {0, 1}</i>: Vehicle <i>k</i> travels from node <i>i</i> to node <i>j</i>.<br>
                &bull; <i>u<sub>k</sub> &isin; {0, 1}</i>: Vehicle <i>k</i> is activated.<br>
                &bull; <i>w<sub>ik</sub> &ge; 0</i>: Cumulative volume load on truck <i>k</i> after visiting container <i>i</i>.<br><br>
                <b>Objective Function:</b><br>
                Minimize total road network distance plus fleet charter activation penalty.
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="glass-box">
            <h4 style="color:#00e5ff;">2. Asymmetric Distance Graph (OSRM)</h4>
            <p style="font-size:0.82rem; color:#94a3b8; line-height:1.5;">
                Urban street networks are intrinsically asymmetric (<i>D<sub>ij</sub> &ne; D<sub>ji</sub></i>) due to one-way streets, divided highways, and turning restrictions. We extract an exact 111 &times; 111 road matrix via OSRM, capturing driving minutes and turn-by-turn road topography.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with f_col2:
        st.markdown("""
        <div class="glass-box">
            <h4 style="color:#f59e0b;">3. Multi-Trip Vehicle Routing (MTVRP)</h4>
            <p style="font-size:0.82rem; color:#94a3b8; line-height:1.5;">
                Trucks dump loads at Böllinger Höfe (Node N+1) in 20 minutes (<i>t<sub>unload</sub> = 20 min</i>) and immediately begin subsequent collection trips. All 4 runs finish in <b>6.45 hours</b> (&le; 8.0h shift limit), meaning <b>1 single physical truck</b> completes the entire daily dispatch.
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="glass-box">
            <h4 style="color:#a855f7;">4. Independent Verification Auditor</h4>
            <p style="font-size:0.82rem; color:#94a3b8; line-height:1.5;">
                The post-solve auditor (<code>verify_gurobi_routes</code>) independently reconstructs every route from raw coordinates, verifying:
                <br>&bull; Exact single-visit coverage of all 24 candidates.
                <br>&bull; Reconstructed road distance matches solver within 0.05 km.
                <br>&bull; Reconstructed shift hours match solver within 0.05 h.
                <br>&bull; Volume (&le; 18 m³), weight (&le; 9,000 kg), and shift (&le; 8.0h) constraints 100% satisfied.
            </p>
        </div>
        """, unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown("""
<div style="display:flex; justify-content:space-between; font-size:0.75rem; color:#64748b;">
    <div>WasteRouting.AI &bull; PreZero Smart Waste &bull; City of Heilbronn Hackathon 2026</div>
    <div>Optimization Engine: Gurobi MILP CVRP &bull; Distance Graph: OSRM Asymmetric</div>
</div>
""", unsafe_allow_html=True)
