# Joint container inventory and collection scheduling

Use **Forecast, routes & simulation → Optimize containers & collection frequency → Find best containers & schedule**. The automatic search chooses physical containers and collection dates per site and glass type, then computes and verifies the daily truck routes. The existing manual comparison remains available. Source data and the active collection draft are unchanged.

## Inputs and assumptions

The baseline count is the assumed capacity represented by each historical percentage. Incoming litres/day are inferred from ordinary historical filling cycles as documented in [capacity planning](capacity-planning.md). That volume is held fixed across inventory choices. Full, overfull and unknown endpoints do not supply exact rates. Unsupported streams are excluded from demand and cost, but reserve their assumed baseline container space at each site.

The configurable defaults are a four-week repeating operating cycle, maximum 90% expected fill, collection gaps of 1–28 calendar days, at most three containers per site/type and nine containers per site in total. These bounds are scenario assumptions, not measured site surveys. Site-specific total-container limits can override the global limit. Cycles can span 1–8 weeks; collection intervals cannot exceed the cycle. Each type present in the model keeps at least one physical container; removing demand or reallocating residents to another site is not modelled.

The confirmed €500 per scheduled truck-day includes truck, driver and driving kilometres. A positive additional €/km is charged only when explicitly entered. Container rental/ownership expense remains unpriced by default. With missing container prices or unsupported inventory, a recommendation is conditional and does not establish a complete financial optimum. Counts must be verified against actual physical inventory before operational use.

## Search and verification

`integrations/joint_planning.py` owns the optimization:

1. Build a periodic calendar over actual operating weekdays. Weekends still accumulate glass. No public-holiday closure is inferred.
2. The CP-SAT master chooses integer container counts and binary per-type visit dates. For every day, including the cycle boundary, the chosen count requires a previous collection close enough to remain below the fill target. Minimum/maximum collection-gap and per-site space constraints also apply.
3. Service time uses actual physical counts, multiplied by the configured emptying minutes per container. A service-time fleet proxy reserves 40% of each shift for driving/unloading; it guides the calendar search and is not a monetary or global-optimality certificate. Conservative per-type shares of payload/volume and configured compartments guide admissible gaps so a same-site combination can fit one load.
4. Search both service-cost and inventory-first strategies, with feasible calendar hints. If a short master run has no incumbent, use a constructed capacity-safe candidate, then require the same actual route checks. Fallback candidates are checked against physical space limits before routing and must pass every final constraint; a master result is not treated as proof about every real-world routing possibility.
5. Remove surplus capacity which cannot affect the chosen calendar's peak occupancy, and remove redundant visits when all cyclic gap limits still hold. This prevents a short solver run from retaining gratuitous containers or collections.
6. Route each candidate through the existing street-network, multi-load engine. Different glass types can be emptied on different days; due types at one site share a stop. Count each selected physical container in service time. Exact road travel, payload, total volume, configured compartments and shift limits determine final feasibility and paid truck-days. Unserved collections remain pending and do not reset their contents.
7. Verify daily fill targets, spill, collection gap bounds, physical space and cyclic end stock. A candidate is eligible only when every supported stream returns to its starting stock, has no pending work or spill, and meets its fill target. Therefore collected cycle volume equals the entire incoming cycle volume; deferring glass beyond the horizon cannot make a candidate look cheap.
8. Keep a feasible baseline as an incumbent and select the least expensive routed eligible candidate, breaking ties by installed containers, working hours and road distance. Verify real street geometry and shift duration before offering its routes. Failed geometry cannot become a dispatch recommendation.

The baseline repeats an evenly staggered calendar with the requested nominal baseline interval, advanced to operating weekdays. Actual resulting gaps and constraint violations are checked. It is compared using the same volume model and period. If it fails the target/bounds, its cost is shown as a service trade-off.

The cyclic starting stock follows the chosen repeating calendar. It is **not today's measured or forecast occupancy**, and this is not a transition plan from an arbitrary initial inventory state. Constant demand and a 10% target buffer do not establish probabilistic or seasonally robust overflow safety.

The master time limit and bounded route searches mean the response is **best feasible found**, never a claim of a proven joint global optimum. A lack of a verified result means the search did not find a dispatchable plan within the given bounds, not that every conceivable real-world schedule is impossible.

## Outputs and UI

The response adds `optimization` to the request-local capacity result: status, solver strategy outcomes, candidate checks, recommended count and achieved mean/maximum collection interval per site/type, expected maximum fill, and exact scheduled collections. Each recommended date includes truck shifts, service totals, ordered multi-load routes and real street geometry.

The UI provides a daily shift calendar, date-specific OpenStreetMap truck/load inspection, inventory/frequency filters and pagination, the existing average filling-time and daily-shift graphs, financial comparisons and an escaped CSV of actual date/truck/load/stop/type/count/volume. Deterministic target-based stops do not invent overflow probabilities.

Completed results and form values survive switching workspace modules within the current Nuxt session. Cache context includes cutoff, applied operating settings and uploaded dataset. Changes to inputs or context clear the result; in-flight work is cancelled and stale responses cannot restore an old financial result. Cached results are request/session-local; no database or shared model state is written.

Optimization requests have an eight-minute engine limit; manual comparisons retain four minutes. The browser allows a small transport margin. A warm street cache improves subsequent runs. Prepare a completed scenario before a short pitch, then use the retained results for the demonstration.

## Checks

`forecast_service/tests/test_joint_planning.py` covers cyclic volume conservation, paid-shift costs, count/calendar/route output, weekend storage, target/space/interval infeasibility, unknown-history space reservation, missing coordinates, geometry failure, fallback seeds, future-data exclusion and removal of surplus containers. The relocated stdin worker test also runs the automatic mode independently of contributor directories.

API endpoint tests bind and validate automatic mode, cycle, fill target, count/interval bounds and per-site limits while preserving inclusive cutoff and upload isolation. Frontend tests cover automatic button binding, stale-request cancellation, result retention/invalidation, inventory pagination, date-specific maps, CSV escaping and hiding dispatch/export for an unverified result.

## Full-data integration check

On the Karlsruhe demo snapshot through 30 September 2026, the four-week, 90% target run covered 1,298 supported site/type streams; 40 streams lacked ordinary-cycle support. Both baseline and recommendation collected 2,027,918.802 litres over the cycle with no spill or fill-target violations and with matching cyclic start/end stock. The weekly baseline used 80 truck-days (€40,000); the bounded search returned 48 truck-days (€24,000) and 1,474 modelled physical containers versus 1,298 in the baseline. The €16,000 difference is in modelled truck-package expense only: 176 additional containers are unpriced, unsupported inventory is excluded, coordinates/history are synthetically assigned and constant-rate demand is assumed. It is not measured savings or a complete financial optimum. Solver results may vary.

Browser verification replayed that independently verified live API result to check automatic mode/bounds, actual returned street geometry, date changes, inventory filters/pagination, CSV rows matching every scheduled collection, module-navigation retention without another calculation, mobile bounds and immediate invalidation after changing the fill target. No page errors occurred.
