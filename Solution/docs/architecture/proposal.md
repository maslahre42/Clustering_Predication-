# Forecast and route proposal

`GET /api/proposal?asOf=yyyy-MM-dd` answers: which containers should be emptied on the next collection day, with how
many trucks, in which order. The web module is **Forecast & route proposal** in the sidebar.

The logic was taken from the team's three prototypes and rewritten in C# without external solvers:

| Part | Taken from | What was kept |
| --- | --- | --- |
| Reading semantics, filling cycles, overflow probability, selection rule, multi-load routes, settings with source labels | Omar | A visit empties the bin; full/overfull mean "at least 100%"; risk before the next collection day; neighbours at a visited site; trucks unload and continue |
| Rejecting invalid input by name, a reason for every bin and every unserved stop, loads kept apart from trucks | Kaise | Nothing is clipped or dropped silently |
| Simple rate per bin with fallback to the glass type, strict history cutoff, fleet first | Zakaria | Bins with few visits borrow from their glass type |
| Cutoff rules, bin identity, manifest and export | Monir (existing app) | The proposal can be handed to the Collection plan |

## Method

1. **Cutoff.** Only observations through `asOf` are read (same inclusive rule as the rest of the app). The proposal is
   for the first collection day *after* `asOf`, so no reading of the plan day is used.
2. **Filling cycles** (`FillingCycles.cs`). Fill at a visit ÷ days since the previous visit = fill rate of that cycle.
   Differences between readings are never used. Unknown readings still empty the bin but give no rate.
3. **Fill-rate model** (`FillRateModel.cs`). Log-normal daily rate per bin, pulled towards the average of its glass type;
   full and overfull cycles are lower bounds. Fitted by expectation-maximisation, deterministic, about 0.1 s.
4. **Selection** (`CollectionPolicy.cs`). *Due*: overflow probability by the next collection day ≥ 0.70. *Neighbour*: at a
   site with a due bin and (probability ≥ 0.12 or expected fill ≥ 40%). *Optional*: same test at a site whose highest
   probability is ≥ 0.40. Everything else is skipped. A Friday plan looks ahead to Monday.
5. **Routes** (`RoutePlanner.cs`). Mandatory sites first, most urgent first (nearest first when coordinates are used).
   A truck unloads when the next stop would exceed the load limit, continues, and finishes with a last unload and the
   drive back inside one shift. A new truck opens only for mandatory sites. Optional sites use spare time only.

Defaults are the numbers PreZero gave on 14 November 2026 (3 m³, 12 t per load, 8 h, 10 min per drive, 5 min per
container, Monday to Friday). Density 350 kg/m³, 15 min unloading, yard and unloading-site positions are assumptions.

## Evidence on the challenge data (11,701 readings, 17 Oct 2025 to 30 Sep 2026)

Run on 14 November 2026 against the real file.

| Test | Result |
| --- | --- |
| Forward test, trained through 31 March, 6,657 later visits | Mean error 19.7 points; AUC 0.78 for "fill ≥ 70%" (Omar's Python model: 19.5 and 0.78) |
| Same, refitted at the start of each month (how the endpoint behaves) | Mean error 18.5 points; AUC 0.80 |
| Proposal for Monday 17 August 2026 | 49 mandatory sites, 4 trucks, 14 loads, 68 sites, 168 containers, 31.8 h in total |

**Known weakness: the risk is too high in summer.** When the model said 80–100% overflow risk between April and
September, the bin was actually full in 66% of cases (60–80% predicted: 50% observed). Inside the training period the
probabilities match. The history starts in October, so winter (with Christmas) dominates and no seasonal effect can be
fitted from less than one year. The plan is therefore cautious: it visits somewhat more than necessary. Weighting recent
visits more was tried and made the forecast worse, so it is not used.

## Limits

- Routes are a constructive heuristic: feasible, few trucks, not a proven optimum. With the fixed 10-minute rule the
  order of stops does not change the time, so the remaining question is packing loads and shifts.
- No seasonal, holiday or weather effect. No colour chambers, lifting equipment, access or time windows.
- Site coordinates in `sql.db` are synthetic; in coordinate mode distances are straight line × detour factor.
- Handing a proposal to the Collection plan keeps the stop order but not the split into trucks.

## Tests

`tests/GarbageCollector.Api.Tests/Proposal/` (101 cases) and `tests/proposal-*.test.mjs` (18 cases). The tests were
written before the implementation.
