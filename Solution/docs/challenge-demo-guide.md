# Challenge submission and demo guide

Updated 15 November 2026. The live application now uses car-street routing and coordinated truck sectors. Earlier fixed-time and straight-line demonstration results in the historical verification documents do not describe the current engine.

## Challenge deliverables

| Deliverable | Demonstration |
| --- | --- |
| Ingest readings | Forecast module's validated CSV upload; invalid rows and duplicate keys are rejected without silently modifying source data. |
| Patterns, groups and anomalies | Historical analytics: partial-month charts, numeric/censored cycle evidence, distributions and review flags. Forecast supporting details: quality gates, groups, month/vacation associations and uncertainty. |
| Configurable operations | Container/density, truck payload/volume, available fleet, shift/calendar, service/unloading time, yard/disposal coordinates, risk rules and search budget. |
| Route and fleet proposals | OSRM car-street costs, compact truck sectors, OR-Tools multi-load routes, explicit unserved stops, map inspection, manifest and CSV export. |
| Documentation | This guide, [street routing](architecture/street-routing.md), [forecast method](architecture/proposal.md), [integration contract](combined-project-integration.md) and [setup](../README.md). |

## Demonstration

1. From `Solution/`, run `make setup` on a fresh checkout, then `make run`. Open `http://localhost:3000`.
2. Select **2026-09-30** and open **Historical analytics**. The source has **11,701 readings, 449 locations and 1,338 observed location/material bins**, from **2025-10-17 to 2026-09-30**.
3. September brown glass has **221 collections, 9 overfull and 34.2% numeric mean fill**. Selecting **2026-09-08** gives **9, 0 and 28.9%**, explicitly marked as a partial month. Counts are bin emptyings, not trucks or unique site visits.
4. Compare the monthly count/fill charts, cycle-rate evidence and flagged containers. Open a flagged location to inspect its source history. Full and overfull are lower bounds; unknown visits reset intervals but supply no rate. Low-fill flags are review prompts, not proof of unnecessary visits.
5. Open **Forecast, routes & simulation**. Review the operating numbers and apply changes. The first street plan may take longer while road data is cached. There is no fixed-time challenge switch or aerial-distance mode.
6. In **Follow the collection route**, select one truck and load. Streets follow the OSRM road geometry. Direction/sector labels show which part of the region belongs to each truck. Click stops for details; inspect unloading visits, fit/expand the map and optionally show unserved sites. A truck keeps its sector across loads and returns to the yard after final unloading.
7. Review road kilometers, truck loads, working time and any missed mandatory stops. Payload and shift limits remain hard constraints. Optional collection value defaults to zero to avoid rewarding extra driving for non-urgent sites. Increasing it is an explicit service/cost trade-off.
8. Accept the proposal into the collection manifest and export CSV or print the collector sheet. The manifest retains truck/load assignments and street geometry. Changing the date clears the draft.
9. Explore an individual forecast curve, then run a short **Simulation & backtest** window, e.g. **2026-08-10–2026-08-10**, seed **7**, one-second daily attempts. Historical, Omar and Zakaria policies use the same road provider, constraints and demand. Compare street kilometers beside work and missed service. The real-reading forecast comparison and bounded Gurobi check have separate meanings.
10. Upload readings to demonstrate strict validation and dataset isolation. CSV-only uploads can be forecast and analyzed; road routing needs matching site coordinates. Missing locations are reported, not replaced with original-inventory points or fictional journeys. Uploaded-data proposals are exported directly rather than attached to the unrelated original manifest.

Reading format:

```csv
Location_id,material_type,date,fill_level_perc
demo-site,white,2026-07-01,30
demo-site,white,2026-07-11,50
demo-site,white,2026-07-21,70
demo-site,white,2026-07-31,60
```

## Meaning of returns and apparent overlap

Unloading can be necessary before a truck reaches its nominal payload when the next indivisible site pickup will not fit. Every load has an unloading visit, and the last load also returns to the yard. Nearby yard/unloading points can make these legs look like repeated yard returns. The optimizer now keeps pickup ownership in compact sectors; common access roads and the shared depots can still overlap.

Street kilometers are a genuine road-network measure for the supplied coordinates. They are not proof of measured fuel savings or verified bin locations. Comparing two plans requires the same served bins and constraints: leaving urgent stops unserved cannot count as an efficiency improvement.

## Verification and reproducibility

```sh
make test
make typecheck
make build-api
NUXT_BUILD_DIR=.nuxt/street-build make build-web
API_BASE=http://localhost:5080 python3 scripts/smoke-test.py
```

Latest executed unit/build and browser results are described in [street-routing verification](architecture/street-routing.md). Public settings have no fixed-time/speed/detour overrides. Source SQLite is still byte-identical to its Git version. Live OSRM checks returned real road matrices and full street geometry; unit tests use explicit provider doubles and do not depend on the internet.

The current prototype covers the challenge workflow. Operational use still needs verified coordinate mappings, actual depots, measured loads, an appropriate road service and truck access rules. Durable plans, authentication, electronic dispatch and driver completion remain extensions. Configured glass chambers now constrain every policy; actual capacities must be supplied. Car routing does not verify heavy-truck legal access. The source spans less than a year, so seasonal/holiday associations and short-window evaluation results require cautious interpretation.

## New planning controls and presentation

In **Forecast, routes & simulation**, expand **Glass compartments** and enter the actual brown, green and white capacities together. Leave all three zero for unknown layout. Expand **Operating costs** for variable €/road-km and fixed €/scheduled-truck-shift; leave unknown prices unpriced. Apply to recalculate. The route table includes colour volume per load, and accepted manifests retain the cost estimate.

Use **Save current plan as baseline**, edit fleet/payload/shift/compartments/thresholds, then apply. The comparison shows road km, truck shifts, loads, completed containers, costs and missed urgent sites together. A reduction is only shown for matched completed service and comparable inputs. Baselines clear when date or dataset changes.

The time-to-full table gives cutoff-relative days, estimated dates and a 10–90% model range, with explicit missing history. **Present this plan** opens six live-data slides. Use arrows or Previous/Next, Escape to close, and the final slide to download the route sheet. See [planning insight rules and tests](architecture/planning-insights.md).

## Collection cadence and filling dynamics

**Historical analytics → Understand past collections** now includes glass-specific inter-visit and filling-speed histograms, median/IQR summaries, a cumulative projected time-to-full curve, and fastest/slowest container rankings. Change the glass fraction or ranking, then click a location to inspect it. Recorded collections and completed intervals are shown separately. Unknown, zero and full/overfull cycles remain distinct; the chart labels which cycles support an estimate. A 28-day guide is a comparison rather than an assumed schedule. See [calculation and cohort rules](architecture/collection-dynamics.md). Public model and simulation labels describe their methods without contributor credits.

## Fill after emptying on the selected date

The planner defaults to **Selected-day estimate**. A recorded 30 September collection resets the modeled bin to zero; selecting 1 October shows estimated new fill, rather than repeating its old full reading. Use **Fill view → Last recorded before emptying** for the historical measurement. Fill filters, ordering and location details follow that selection. Dates and proposals do not execute collections; only recorded visits reset state. Missing estimates remain unknown. See [selected-day behavior and real-data verification](architecture/selected-day-fill.md).

## Provider-focused financial demonstration

Open **Forecast, routes & simulation → Compare containers & collection frequency**. Keep baseline counts as explicit inventory assumptions; change alternative counts by glass type or a particular site. Compare 7-day and 14-day intervals over the same 28-day period. The confirmed €500/truck-day includes truck, driver and driving kilometres; leave additional €/km at zero. Add monthly container costs when known. Run **Compare financial impact**. Lead with the period/monthly-equivalent expense, then show average filling-time bars and daily shifts. Read spill, pending sites, remaining glass and unsupported inventory alongside costs; do not describe a lower total as a saving when service differs.

The first live API check on the Karlsruhe demo used seven days with identical baseline/alternative settings: 1,298 supported site/type streams, 40 without ordinary-cycle support, no missing coordinates, 20 truck-days and €10,000 in priced truck/driver expense. The two outputs were exactly identical. The initial check marked road/container expense unpriced; the provider subsequently clarified that driving kilometres are included in the €500 package, and source-to-site assignments remain synthetic. These are an integration check with stated assumptions, not validated operating costs or measured savings. The paired-intervention behavior is covered by capacity/frequency regression tests.

## Automatic recommendation for the provider

Open **Optimize containers & collection frequency** and verify assumed baseline counts, container prices and physical site limits. Set the fill target (default 90%) and repeating cycle (default four weeks), then run **Find best containers & schedule**. Prepare this calculation before the five-minute pitch; the first uncached street calculation can take several minutes. Completed results survive switching workspace modules with the same inputs. Show the recommended counts and frequencies, paid truck-day cost, fill-target checks, daily shift calendar, one date on the street map and the CSV export. State that the recommendation is the best feasible found for constant demand and the chosen bounds, with unpriced container expense and unsupported history disclosed.
