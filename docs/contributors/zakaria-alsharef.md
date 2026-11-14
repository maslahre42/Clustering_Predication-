# Zakaria / Zakarea Alsharef — exploratory analysis and modular optimization pipeline

> **Subsequent correction:** This report records the implementation reviewed before the correction task. The current pipeline preserves Zakaria's notebook/Gurobi approach while addressing the documented overflow, cycle-rate, cutoff, site-accounting and solver issues. See the [current README](../../Zakaria-Work/README.md), [method changes](../../Zakaria-Work/docs/corrections-and-method.md) and [verification](../../Zakaria-Work/docs/verification.md). Historical criticisms below should not be read as a fresh assessment of the revised code.

## Contribution and attribution

Git author `Zakarea Alsharef` contributed the original exploratory `main.ipynb` in commit `13d53f3` (`initial pipeline`). The current [Zakaria-Work](../../Zakaria-Work/README.md) folder includes that notebook plus four modular notebooks, reusable Python modules and a geographic reference file. The current `main.ipynb` was verified byte-for-byte against the committed original. The expanded folder is untracked, so its association with Zakaria comes from the folder name and local content; the original commit does not establish authorship of every later module.

The substantive work turns a challenge dataset into descriptive charts, location behavior groups, forecast physical demand and a Gurobi vehicle-routing proposal. The challenge documents and presentation bundled in the folder are supplied brief material, not evidence that Zakaria authored them.

## Business workflow and artifacts

| Stage | Entrypoint | Output / business use |
| --- | --- | --- |
| Exploration and cleaning | [01 notebook](../../Zakaria-Work/01_eda_and_analysis.ipynb) | `data/cleaned_fill_levels.csv`; material/calendar/visit summaries |
| Behavioral profiles | [02 notebook](../../Zakaria-Work/02_container_clustering.ipynb) | `data/container_clusters.csv`; four operational tiers |
| Demand projection | [03 notebook](../../Zakaria-Work/03_fill_prediction.ipynb) | `data/predicted_demands.csv`; future percentage, volume, mass, urgency |
| Vehicle assignment/order | [04 notebook](../../Zakaria-Work/04_gurobi_route_optimization.ipynb) | Vehicle summaries and `route_proposal.html` |

CSV intermediates decouple notebook execution, allowing demand/routing changes without rerunning plots. Notebook fallbacks rebuild missing upstream inputs, but these outputs are generated workflow artifacts, not all guaranteed present in the current tree. This is a notebook/library pipeline rather than a connected HTTP service or deployed dashboard.

## 1. Data loading and calendar enrichment

Source: [data_loader.py](../../Zakaria-Work/src/data_loader.py).

The loader looks for the requested CSV and then the same path beneath `PreZero/`. It removes BOM/header whitespace, parses dates, marks case-insensitive trimmed `overfull`, and numerically replaces that category with 110. Other values are cast directly to float. It sorts by `(Location_id, material_type, date)` and adds year/month, weekday name/index and ISO week number.

Baden-Württemberg statutory holidays for 2025/2026 are marked through the `holidays` library. The flag also covers 20 December–6 January and dates within three days before/after holidays. It therefore means a broad holiday/festive window rather than only actual public holidays. Holiday tags explain the match.

Per location/material, it shifts the prior date and numerical fill, then computes elapsed days and fill differences. `get_latest_readings` groups by location/material, while the profile helper discussed below groups by location after an optional material filter. The loader has no structured reject/accept validation report, duplicate resolution or numeric-range enforcement; invalid values can fail parsing or propagate.

## 2. Original exploratory workbook

Source: [main.ipynb](../../Zakaria-Work/main.ipynb), 22 cells.

The original workbook builds dataset counts, fill distributions and glass-material benchmarks; plots daily material mean/IQR with example bin histories; examines monthly means and explicit overflow rates; proposes a visit-efficiency audit; groups locations; and defines potential operating variables and a future product workflow.

Its business comparisons highlight white/green/brown differences through mean/median visit fill, explicit overfull shares, ≥100 shares and ≤30 shares. Daily means and percentile envelopes summarize the bins visited on those dates; they are not simultaneous measurements of the entire network. Calendar shading and explanations suggest Christmas/Easter/Pentecost effects, but do not fit a causal seasonal model.

The original audit treats a negative difference between consecutive readings as an emptying, then classifies the prior reading:

- ≥100: late/overflow.
- 70 to below 100: “optimal” (the label says 70–90 although arbitrary values below 100 also qualify).
- 40 to below 70: premature.
- Below 40: highly inefficient.

Its original clustering pools materials at location level, uses mean/std fill, explicit overfull share and mean positive difference/day, standardizes them and fits K-Means with four clusters, seed 42 and ten initializations. Missing positive rates fall back to a pooled median. Cluster names follow centroid thresholds: overfull rate above 15 → chronic overflow; otherwise mean above 65 → high-volume, above 50 → moderate, else low-volume. Distinct clusters can receive the same tier name.

These are implemented exploratory rules; their operational validity depends on reading semantics. Under the other prototypes' pre-emptying/reset interpretation, consecutive visit differences do not measure uninterrupted accumulation, and negative differences do not identify collections. Consequently the old workbook's “44.4% late / 26.2% premature” interpretation is not an independently valid efficiency benchmark.

## 3. Modular EDA and profiling

Sources: [01 notebook](../../Zakaria-Work/01_eda_and_analysis.ipynb), [clustering.py](../../Zakaria-Work/src/clustering.py).

The first modular notebook reuses the cleaner and reports counts, material distributions, weekday/monthly patterns, festive-window comparisons and the same negative-difference audit before exporting cleaned data.

The profiling helper accepts an optional material filter. The demonstrated second notebook explicitly filters to white glass, then groups by location. For each profile it computes reading count, numerical mean/std/max, literal overfull percentage, latest reading/date and a median nonnegative difference/day where elapsed days are positive. Missing velocity is replaced by **0.65 percentage points/day**, and missing std by zero. Zero differences are included in this modular velocity estimate; the original notebook used strictly positive differences.

Because profile aggregation keys only on location, callers who omit the material filter pool colors and select a single latest row across colors. “Current fill” is simply the renamed last recorded pre-visit value; the code does not estimate intervening resets or align every location to one common planning date. Also, pandas `groupby().last()` selects last non-null column values, so incomplete rows can combine fields from different source rows.

## 4. Four behavior tiers

Source: [cluster_containers](../../Zakaria-Work/src/clustering.py).

The modular clustering features are mean fill, std fill, literal overfull rate and daily velocity. `StandardScaler` gives each dimension comparable scale. K-Means defaults to four clusters, seed 42 and ten initializations. Clusters are ranked by average mean fill plus average overfull rate, then named:

1. Critical / Chronic High-Volume.
2. Steady High-Demand.
3. Moderate Regular.
4. Low-Demand / Sporadic.

The labels express a priority ranking; there is no balancing constraint, minimum cluster size or silhouette/separation gate. The README's description of “balanced” tiers is therefore stronger than the implementation. The reusable function cycles tier names if more than four clusters are requested. Full-history features and last readings are used, without an `as_of` restriction or held-out validation.

## 5. Forecasting, volume, weight and urgency

Source: [predictor.py](../../Zakaria-Work/src/predictor.py).

```text
growth = daily_fill_velocity × days_ahead × holiday_multiplier
predicted_fill = round(min(110, current_fill + growth), 1)
volume_m3 = round(predicted_fill / 100 × container_volume_m3, 2)
weight_kg = round(volume_m3 × density_kg_m3, 1)
```

Defaults are two days, multiplier 1.0, container 2.5 m³ and density 380 kg/m³. Notebook 03 explicitly uses multiplier **1.20**; it is a supplied scenario assumption, not a coefficient learned from holiday data. Urgency is urgent ≥80%, opportunistic 60–below 80%, safe below 60%.

For example, a recorded 75% plus 2 pp/day over two days with a 1.20 multiplier produces 79.8%, classified opportunistic. At 110%, the physical demand can exceed nominal capacity. The predictor rounds volume before calculating weight; the optimizer recomputes unrounded volume from the percentage, so exported predicted weight can differ slightly from solver demand.

This is deterministic linear extrapolation, with no uncertainty, model training, probability calibration, forecast evaluation or lower-bound clipping. Neither sparse-data 0.65 velocity nor a 110% overflow amount is measured ground truth. Starting from a pre-emptying observation as if it were still in the bin also ignores the reset after the visit.

## 6. Geographic distance abstraction

Source: [distance_provider.py](../../Zakaria-Work/src/distance_provider.py).

`ModularDistanceProvider` has two modes:

- If a provided table contains `Location_id,lat,lon`, merge by candidate ID and use those coordinates. Missing matches are not validated and can create NaN distances.
- Otherwise generate a seeded clipped-normal Heilbronn-area point cloud around a fixed center. Compute pairwise haversine distance × 1.30, then normalize the off-diagonal mean to 1.4 km by default.

Depot-to-zone distance defaults to a constant 4.5 km per candidate, candidate-to-disposal to 5.5 km, and disposal-to-depot to 3.2 km. Even “REAL_GPS” mode keeps those fixed depot/disposal distances; it is not an end-to-end real road matrix. Synthetic normalization also makes distances depend on the candidate batch rather than a permanent city network.

The folder contains [mapped Heilbronn container references](../../Zakaria-Work/data/heilbronn_actual_glass_containers.json), with POI IDs, street names, UTM and latitude/longitude. The demonstrated routing notebook does not load this file. It has no verified join to anonymized historical UUIDs; possession of real reference coordinates does not establish actual historical bin identity.

## 7. Candidate selection and Gurobi MILP

Sources: [04 notebook](../../Zakaria-Work/04_gurobi_route_optimization.ipynb), [optimizer.py](../../Zakaria-Work/src/optimizer.py).

The demo takes `head(24)` from rows classified urgent. It does not sort them by descending risk/fill, optimize which candidates to include, route opportunistic bins, or account for the remainder as unserved. This cap is a demonstration subset, not a complete city plan.

For `N` candidates and up to `K=4` vehicles, the model defines depot node 0, candidates 1…N and disposal N+1. It computes demand from predicted fill, falling back to `current_fill_perc`, using configurable density and capacity. Defaults are 18 m³ truck volume, 9,000 kg payload, 7.5-hour shift, 28 km/h speed, six-minute service and twenty-minute final unloading.

Decision variables are binary arcs `x[i,j,k]`, candidate assignment `y[i,k]`, vehicle-used `u[k]` and continuous MTZ order variables. The objective minimizes traveled kilometers, disposal return distance and **25 km-equivalent per used truck**. Fleet size is a cost trade-off, not a strict lexicographic minimum.

Constraints require every supplied candidate assigned exactly once; inflow/outflow to match assignment; a used truck to leave the depot and reach disposal exactly once; total load below both volume and payload capacities; and driving + service + unloading within the shift. Miller–Tucker–Zemlin inequalities prevent disconnected candidate subtours.

Only arcs depot → candidate, candidate → different candidate, and candidate → final disposal exist. Trucks cannot unload mid-route and resume collection. Each vehicle makes one collection tour followed by one unloading and a return to the yard. Color chambers, equipment matching, breaks and time windows are not enforced, despite some appearing in the original notebook's proposal.

Gurobi runs silently with a default twenty-second limit and 5% MIP gap. A local license is used if present, and a Windows `.venv` bundled-license fallback handles detected license errors. If an incumbent exists, routes are extracted even without proof of optimality. If none exists, the function returns an empty DataFrame without distinguishing infeasibility, timeout or an empty candidate set in the returned contract.

Outputs report truck ID, candidate order/UUIDs, stop count, total volume/weight, capacity utilization, distance and shift hours. A feasible solution only covers the supplied 24-row subset, not all urgent city bins.

## 8. Map and collection presentation

Source: [visualizer.py](../../Zakaria-Work/src/visualizer.py).

Folium plots a yard, an illustrative disposal point offset from the center, truck-colored stops, sequence numbers, UUID prefixes and predicted percentages, then draws yard → stops → disposal → yard. The map is saved to HTML even for an empty plan.

Lines connect coordinates directly. The optimizer's depot/disposal distances are constant parameters and synthetic inter-point distances may be rescaled, while map polylines follow generated/raw coordinates. Therefore map line lengths and reported modeled kilometers need not agree. The notebook/README's “turn-by-turn” wording is not supported by maneuver instructions, road routing or a navigation export in the source.

## 9. Proposed operations versus implemented operations

The original workbook defines a `FleetConfig` for a 12 t/24 m³ truck with separate white/green/brown chambers, seven-minute service, eight hours and a 45-minute break, plus material densities and 3 m³ containers. It proposes dynamic trigger thresholds and a future OR-Tools/Streamlit-style application. Those configuration objects and proposals are distinct from the modular Gurobi defaults and constraints. They must not be described as enforced chamber or break logic.

The implemented business deliverable is reusable exploratory analysis plus an understandable demand-to-CVRP pipeline. It demonstrates how changes to physical and time assumptions affect candidate routing. It does not establish observed operational savings, a calibrated predictor, minimum city fleet, a full dispatch application or road-feasible navigation.

## 10. Verification and limitations

No dedicated automated test directory is present in `Zakaria-Work/`. Notebook source and reusable modules were reviewed; Gurobi, notebook cells and generated maps were not executed in this documentation task. An available valid license and Python dependencies are required to reproduce optimization.

Priority interpretation gaps are the invented 110% value, difference-based collection/growth inference under pre-emptying semantics, full-history feature leakage for historical decisions, last reading mislabeled current fill, no candidate-date alignment, arbitrary unserved demo remainder, and a solver return that does not explain failure status. These observations describe the current behavior and do not erase the useful modularization, charts and mathematical routing formulation contributed here.
