# Container capacity, collection frequency and financial comparison

For automatic count/calendar selection and verified daily routes, see [joint planning](joint-planning.md). The manual comparison below remains available.

The provider's main decisions are physical containers at a site and the interval between emptyings. The `Compare containers & collection frequency` panel appears before route results in Forecast, routes & simulation. It compares two explicit scenarios without modifying source history or the active collection plan.

## Controls

- Independent baseline/alternative brown, green and white counts, 1–20 per site/type present in history. Optional site/type overrides replace these defaults. Counts are physical containers, distinct from the three glass-type streams represented by historical UUID/material pairs.
- Independent collection intervals, 1–28 calendar days; 7 means weekly, 14 means fortnightly. A 7–31 day comparison starts the day after the selected inclusive history cutoff.
- Container expense per physical container per month. Operating settings supply truck-day, road expense, payload/volume/compartments, service/unload times, fleet size, shifts and working weekdays.
- **Confirmed by the user on 15 November 2026: €500/day includes truck, driver and driving kilometres.** Both API and frontend now default `fixedTruckCostEuro` to 500. It is charged per truck-day, not per load or service hour. No separate driver charge is added. Zero additional €/km means driving is included. Container expense remains unpriced.

## Common demand and filling-time graph

Use only observations through the cutoff. Each recorded visit resets its stream; the next ordinary numeric percentage divided by elapsed days supplies an observed percentage/day. Keep zero rates, exclude unknown/full/overfull cycles from exact estimates, and take the median ordinary rate per stream without the reference model's rate floor.

Incoming litres/day = median percentage/day ÷ 100 × baseline count × per-container litres. Baseline count is explicitly the assumed physical capacity represented by historical percentages; the source does not establish actual physical inventory. Feed **the identical incoming volume** into both scenarios. Different glass types retain separate capacity.

Average filling time is the arithmetic mean of scenario capacity / incoming litres per day across positive-demand streams of each type, with equal weight per stream. Doubling same-type capacity doubles its estimated days to full at constant demand. Changing collection frequency does not change incoming demand or intrinsic filling time. Zero-demand streams have no finite time-to-full. Display supported/positive/zero stream counts and ordinary-cycle counts. This is a constant-rate planning estimate, not a seasonally calibrated prediction or measured overflow time.

Unsupported streams are listed and excluded from modelled capacity, demand and costs, with a prominent partial-inventory warning. No material-level borrowing invents missing rates. CSV requests remain isolated and source data is untouched; the current readings-only CSV path has no location coordinates, so its supported sites remain pending unless a future coordinate import is added.

## Daily operations and service outcomes

Both scenarios start empty. Distribute sites deterministically across interval phases by sorted site order. Each date adds common incoming volume; excess above capacity is reported as spilled volume, and stored volume remains capped. A scheduled stop waits until a selected operating weekday. Missed stops remain pending and retry on later working days. No public-holiday closure is assumed.

Every served site empties all supported glass types and all configured physical containers there. Container count changes service time; glass volume determines truck payload. The existing street-network router enforces weight, total volume, optional glass compartment capacities and shift limits, including intermediate/final unloads and yard returns. A site must fit one load; splitting a single site across trucks is not implemented. Missing coordinates never fall back to depot coordinates or straight-line routes.

Per-day output includes served sites, physical containers emptied, truck shifts, road km, hours, pending sites and spill. Aggregate output includes truck-days, peak concurrent daily trucks, emptying hours, total working hours, remaining glass, glass exceeding capacity and full site/type stream-days. Check volume conservation: generated = collected + remaining + spilled.

Identical inputs reuse the same routed realization, preventing wall-clock solver variation from masquerading as benefit. Distinct scenarios can still vary with bounded solver execution. Route searches are capped at one second per attempt to keep a month-scale comparison bounded.

## Financial interpretation

Period expense = truck-days × €/truck-day + street km × €/km + installed containers × €/container/month × period days / 30.4375.

Round expense categories to cents, then sum. Monthly equivalent = priced period expense × 30.4375 / period days. It is a normalized period estimate, not a validated future calendar month or annual saving. Unpriced categories remain visibly unpriced; the total contains entered categories only. The daily package includes driving; zero additional €/km is not a missing price. Add a positive distance charge only for a fee outside the package. Avoid overlapping costs between rates.

Show signed alternative-minus-baseline cost differences beside demand, collected volume, remaining volume, spill and pending work. A service comparison is allowed only with complete supported inventory and coordinates, no pending sites at either period end, no increased spill and at least as much collected volume in the alternative. Otherwise explicitly label the result a cost/service trade-off, not a savings claim. Even an accepted comparison is modelled, and costs can remain partial.

## Ownership and verification

- API: `Features/Proposal/CapacityPlanning.cs` validates body plus operating query settings, bounds source observations, and calls the request-local Python bridge with action `capacity`.
- Worker: `integrations/capacity_planning.py` owns demand inference, capacity changes, scheduling, routed service and financial aggregation. `worker.capacity_scenario` adapts validated source data.
- Web: capacity contracts, `domain/capacity.ts`, `state/createCapacityPlanning.ts`, and `CapacityPlanning.vue` / `CapacityResults.vue`. Changes to inputs, history cutoff, uploaded dataset, applied settings or dirty status abort old calculations and hide stale costs.
- Regression checks: constant demand, doubled capacity and service time, cadence impacts, zero/censored/unknown/future data, scoped overrides, mass conservation, unserved bins, missing coordinates, exact identical-input results, real router integration with a deterministic street provider, endpoint binding, upload isolation, client validation/cancellation and actual form/result rendering.
