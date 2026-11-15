# Corrections and optimization of Zakaria's pipeline

This revision keeps the original notebook sequence, K-Means exploration, linear rate interpretation, Gurobi mathematical formulation and Folium output. It changes the assumptions and implementation where they made historical interpretation or route feasibility unreliable. Raw challenge observations and geographic reference files remain untouched.

## Reading semantics

The working interpretation, recorded in the team's mentor notes, is that a row measures a bin **before it is emptied at that visit**. Thus a bin is `(Location_id, material_type)`; every recorded visit is already a collection observation. Differences between successive visit readings do not identify emptyings or within-cycle growth.

`overfull` retains its raw text and boolean flag with no numeric percentage. Numeric means omit it. Numeric 100 and overfull are distinct observations, although both make a filling-cycle rate a censored lower bound. Holidays are generated for the actual dataset years; public holidays and the Christmas/New Year window have separate labels. Calendar associations remain descriptive.

The CSV boundary rejects invalid dates/materials/ranges and duplicate bin/date keys explicitly. Whitespace, UTF-8 BOM and material/overflow letter case are normalized. Invalid input does not silently lose rows or get clipped. The complete last row is selected with `drop_duplicates`, avoiding `groupby.last()` combining older non-null values with newer overflow dates.

## Forecast and historical cutoff

For a completed cycle ending at a visit:

```text
cycle rate = pre-emptying fill at cycle end / days since preceding emptying
```

For numeric 100 or overfull, 100 is a lower bound used only in the model feature. It is not an asserted exact overflow amount. The baseline takes each bin's median completed-cycle rate; if no bin cycle exists, it uses the same material's median of available completed cycles. Without either, the rate and forecast remain unavailable. No 0.65 pp/day default is invented.

Dispatch profiles use observations **strictly before the planning day**. The forecast at target day T is:

```text
estimated fill(T) = clip(cycle median rate × days from last emptying to T
                        × explicit scenario multiplier, 0, 100)
```

The last visit's pre-emptying percentage is not added to that estimate. Every bin shares the same planning/target date. A neutral multiplier of 1.0 is the default; changed multipliers are user assumptions, not fitted holiday effects. These medians do not implement a censored likelihood, confidence band or calibrated overflow probability. Unmeasured glass beside the bin is not converted into invented truck mass.

An inclusive historical review may use the selected day's records; morning dispatch may not. Same-day inclusive profiles and profiles using later observations are rejected by prediction. Future-first-observed bins do not enter the dispatch inventory. Stored profiles record cutoff provenance.

## Behavioral groups

Profiles retain all glass materials separately. K-Means uses numeric mean/std, explicit overfull share and log-transformed cycle-median rate. Fewer than three readings or missing required numerical features is labeled insufficient numeric history. Cluster count adapts to distinct eligible samples; the original maximum of four and seed 42 remain.

Group names describe relative observed fill pressure. Output includes group sizes and sampled silhouette, with no assertion that groups are balanced or well separated. In the example run the silhouette is approximately 0.28; that is evidence to inspect overlapping groups, not four proven service regimes. Changing rate semantics requires refitting the groups.

## Selection and physical stops

Every eligible bin receives a selection reason: no forecast, below threshold, threshold reached, or opportunistic collection at a selected site. Default thresholds remain simple and inspectable: urgent 80%, opportunistic 60%. One location becomes one physical stop. Selected materials share travel while paying five minutes of emptying time per bin.

Demand volume/mass is not rounded before optimization. Density and volume are explicit shared inputs; solver inputs with inconsistent mass/density are rejected. Unknown forecast values cannot enter the solver.

The full selection is preserved. The notebook's 24-site demonstration cap is explicit, priority sorted, and exports all other selected sites with `deferred_by_explicit_demo_limit`. It is never presented as a whole-city completed plan. The CLI has **no implicit cap**; `--max-sites` opts into one. A full request with inadequate fleet or license returns an explicit failure and unserved records.

## Smaller Gurobi formulation

The original model duplicated arc, assignment and order variables for each of K vehicles. The revised homogeneous-fleet CVRP uses binary `x[i,j]`, plus shared cumulative volume, arrival and MTZ order variables per site. Depot departures define fleet use and final-disposal arrivals match that count.

Each required site has one incoming and one outgoing arc. MTZ eliminates disconnected cycles even when demand, service and distance are zero. With uniform density, the effective volume capacity is:

```text
min(truck_volume_m3, truck_payload_kg / density_kg_m3)
```

This is algebraically equivalent to enforcing both total mass and volume. Extracted routes are independently checked against both original limits. Future per-material densities would require independent load dimensions, not reuse of that equivalence.

Arrival propagation and final-disposal/return bounds enforce the shift. Arcs that cannot fit a two-site depot/disposal trip are removed before constructing the model. Tupledict sums build adjacency constraints without repeatedly scanning every arc for each site. A capacity lower bound can reject an insufficient fleet before invoking Gurobi.

The objective is hierarchical: fleet first, then distance, replacing the old arbitrary 25 km truck penalty. Search runs with a fixed seed, one thread, time limit and explicit relative-gap tolerance. An incumbent on time limit is feasible, not proof of global optimality. “Optimal” means Gurobi terminated under its configured tolerances for the supplied subset and assumptions. Multiobjective details follow the [Gurobi reference](https://docs.gurobi.com/projects/optimizer/en/current/features/multiobjective.html).

One truck makes one collection tour followed by final disposal and yard return. Mid-route unloading, color chambers, driver breaks, access and time windows are not implemented. This preserves the original single-tour mathematical scope rather than quietly claiming another engine's capabilities.

License errors, infeasible inputs, time limit with no incumbent and empty demand have distinct result states. A structured `RoutingResult` carries routes, unserved sites, runtime, model size and provenance. The older DataFrame function remains a keyword-compatible wrapper with status/unserved metadata in `attrs`. The code uses Gurobi's normal license discovery and does not rewrite process license configuration or search a Windows-specific virtual environment.

## Consistent geography

A seed and SHA-256 of location ID generate stable synthetic coordinates independent of candidate subset/order. The same yard/disposal coordinates determine all matrix legs and map markers. Matrices are no longer normalized by the current batch's average distance, and fixed invented depot distances no longer contradict the drawn geometry.

Provided coordinate tables must have unique matching IDs and valid finite bounds. Their UUID assignment remains synthetic by default unless the caller explicitly supplies verified provenance. The bundled municipal reference list is not silently joined to anonymized UUIDs.

Distances are haversine × detour, not road distances. Fixed travel time is an independent operational mode; the example uses ten minutes per different modeled place. Multiple bins at one site share the drive. Map captions disclose both synthetic assignment and direct-line geometry. Real route legs require a later road-network integration.

## Evaluation and artifacts

Evaluation rolls forward through actual visit dates from 1 April 2026. Each case builds profiles strictly before its target day; earlier test-period observations can become known for later decisions. Numeric error compares cycle median and last pre-emptying reading on **the same common numeric cases**, excluding explicit overfull truths. Coverage and threshold confusion counts are reported separately. Different available forecast counts mean confusion totals must be interpreted with their coverage.

This tests observed visit predictions, not counterfactual daily occupancy or operational savings. Neither CO₂ savings nor avoided truck-hours is inferred from a short synthetic route.

Corrected artifacts are under `data/corrected/`; original CSV exports in `data/` remain as legacy files and the corrected notebooks never read them. `manifest.json` records source hash, date cutoff, configuration, grouping evidence, actual solver status, served/unserved/deferred totals and the artifacts from that run. A file left from a previous run but absent from that manifest is not an artifact of the current run. Raw inputs are read-only. All notebook outputs were cleared when their assumptions changed; verification executes copies separately to avoid retaining misleading old results.

See [verification evidence](verification.md) for actual tests and example outputs.
