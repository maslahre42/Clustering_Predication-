# Omar Mohab — probabilistic forecasting, routing and simulation

## Contribution and attribution

Omar contributed a complete Python/Streamlit prototype spanning CSV processing, calendar analysis, probabilistic forecasting, risk-based collection selection, constrained multi-trip routing, operational settings and backtesting. The current work is under [Omar-Work](../../Omar-Work/README.md).

Commit `b27bb42`, authored by Omar Mohab, originally adds `fillinq-router/`; merge `b5ec626` uses `omarmohab2001` with the same email. These are one contributor identity. The old tracked paths are locally deleted and `Omar-Work/` is untracked, so the report describes current code without asserting every local extension is present in the original commit. A byte comparison confirms that current forecasting, ingestion, calendar, geography and pattern modules match the original commit, while configuration, policy, routing, simulation, dashboard, runner, tests and some saved results have local differences.

## Business purpose and workflow

The operational question is which glass bins should be collected before the next service opportunity, which additional bins are worth emptying while nearby, and how to serve the chosen sites with limited truck loads and shifts. The pipeline is CSV → clean readings → filling-cycle intervals → fitted rate distribution → per-bin fill/overflow forecasts → mandatory/optional sites → truck routes/reloads → map, trip table and CSV. A separate digital twin compares historical and dynamic collection policies.

## 1. Ingestion, quality and filling cycles

Source: [data.py](../../Omar-Work/fillinq/data.py).

The loader accepts a path or uploaded bytes, detects delimiters, tolerates UTF-8 BOMs and aliases columns to `site`, `material`, `date`, `fill_raw`. It checks required columns, trims IDs, lowercases materials, normalizes dates to whole days and parses fill. An `overfull` token becomes numerical 100 plus an explicit flag; all fill values at 100 are marked censored. Invalid dates/fills are dropped, numerical fill is clipped to 0–100, and duplicate site/material/date rows keep the last value. Container identity is `site|material`, and rows sort by container/date.

This is permissive cleaning, not Kaise's reject-whole-upload validation. Material values are normalized but not restricted to the three expected colors. Converting IDs to strings before missing-value filtering also means the cleaning is not a complete identifier-validity check.

The quality report describes readings/sites/containers, material counts, date bounds, median coverage and gaps, p90 gap, full/overfull/low-fill shares, average visit fill and weekend observations. These are measurements at visits, not continuous occupancy.

Under the code's pre-emptying/reset interpretation, every consecutive pair of readings bounds one filling cycle. The first observation has no prior interval and is excluded from fitting. For subsequent visits:

```text
gap_days = max(1, current_visit - previous_visit)
rate = max(current_pre_emptying_fill, 2.5) / gap_days
```

The 2.5% floor keeps logarithms finite. Unlike a difference-of-readings model, this assumes the previous visit emptied the container. A full/overfull cycle gives a lower bound on the true filling rate.

## 2. Calendar features and descriptive patterns

Sources: [calendar](../../Omar-Work/fillinq/calendar_features.py), [patterns](../../Omar-Work/fillinq/patterns.py).

Calendar code builds a daily 2025–2027 table, marks explicit Baden-Württemberg school-vacation ranges, and optionally adds statutory holidays through the `holidays` package. Vacation fraction counts marked days in `(start, end]` divided by interval length. Dates outside the calendar table fall back to zero contribution. The forecast uses school-vacation fraction and month; the separate public-holiday flags/counts are not an additional fitted predictor.

Descriptive functions aggregate monthly readings/mean/full/low-fill shares, weekday visit counts, material coverage/rates and vacation-versus-school-time interval medians. Site grouping pivots fitted log rates by material, fills missing material rates with column means, joins site full-at-100 share, standardizes features and runs seeded K-Means. Clusters are ordered by fitted average speed and labeled slow through very fast. The UI allows changing group count. This is behavioral grouping, not geographic route partitioning or proof of holiday causality.

## 3. Forecast model and uncertainty

Source: [forecast.py](../../Omar-Work/fillinq/forecast.py), class `RateModel`.

For a filling cycle of container `c`:

```text
log(daily_rate) ~ Normal(container_effect[c]
                         + month_effect[end_month]
                         + vacation_effect * interval_vacation_fraction,
                         sigma²)
container_effect[c] is shrunk toward its material mean
```

The model fits maximum a posteriori estimates with SciPy L-BFGS-B and an analytic gradient. Numeric uncensored cycles contribute a Gaussian log-rate likelihood. Censored cycles contribute log survival probability, expressing “at least this rate” rather than pretending overflow has an exact amount. Month and vacation effects have regularizing priors.

It profiles `sigma` over 0.45, 0.60, 0.75, 0.90 and 1.05 using a weak container prior, estimates between-container spread after a sampling-variance correction, clips that spread to 0.15–1.2, and refits with the resulting pooling strength. Sparse containers borrow strength from their glass material. Approximate container-parameter variance is included in prediction variance; this is not a full Bayesian posterior.

Prediction computes elapsed days since last emptying, adjusts the log rate for target month and vacation share, and returns the analytic expected `min(100, rate × days)` plus exceedance probabilities at requested thresholds. Unknown containers fall back to the inferred material mean, or overall material mean if the material is unknown. Quantiles are capped at 100. Median/quantile time-to-full uses the last-emptying month as an approximation. A helper produces daily log rates for the twin.

One implementation detail matters: prediction uses `max(days, 0.5)` inside logarithms. Therefore a forecast at the exact emptying date can be positive; it is not mathematically an exact zero-reset curve. The capped 100% expected fill does not quantify glass lying outside the bin.

## 4. Overflow policy and opportunistic collection

Source: [policy.py](../../Omar-Work/fillinq/policy.py).

`window_end` advances to the configured Nth next working collection day. With default weekdays and one-day lookahead, Friday's window reaches Monday. It handles working weekdays, not statutory-holiday closures.

For each bin, the system predicts expected fill today, current full probability, full probability at the window end and elapsed time since emptying. Defaults select as follows:

| Rule | Default and effect |
| --- | --- |
| Due bin | Window full probability ≥ 0.70 |
| Mandatory site | At least one bin at the site is due |
| Additional bin at a mandatory site | Probability ≥ 0.12 or expected fill ≥ 40% |
| Optional site | Maximum site probability ≥ 0.40; only eligible additional bins are selected |

A due bin is always included in candidate demand. Site urgency is the maximum bin probability. Chosen bins aggregate to one site stop with bin count, mandatory flag, risk-based value, liters and kilograms. Thus three fractions at one site can share travel/setup while retaining per-bin emptying time.

Example: white glass at 0.75 window risk makes a site mandatory; a brown bin there at 45% expected fill is collected as an extra, even if its own risk is low. A site with no due bin must pass the optional-site threshold before becoming a routing candidate.

## 5. Operational configuration

Source: [config.py](../../Omar-Work/fillinq/config.py).

Defaults are 3 m³ containers, assumed density 0.35 t/m³, 12 t payload, truck volume zero meaning no volume constraint, up to 12 trucks, eight-hour shifts, ten-minute fixed drives, five minutes per bin, zero additional site setup and fifteen-minute unloading. A 480-minute fixed cost per truck expresses a preference for fewer trucks. Depot/disposal coordinates, speed and detour factor remain configurable assumptions. Code/UI label parameters as PreZero-provided, assumptions or planner tuning; these are repository statements, not independently reverified facts in this review.

The Settings page edits displayed parameters and working days, saves JSON, imports/exports settings and resets to defaults. The planner rereads settings, while saved backtests require regeneration. `config_from_dict` ignores unknown keys and casts known values; it does not impose all UI minimum/maximum ranges on imported JSON. Invalid operational combinations can therefore reach policy or solver code.

## 6. Coordinates and travel rules

Source: [geo.py](../../Omar-Work/fillinq/geo.py).

A complete `site,lat,lon` CSV is used if it covers every site; otherwise seeded synthetic locations are generated around six Heilbronn-area district centers. Completeness controls the “real” flag; coordinate bounds and actual site identity are not established by this loader.

With `fixed_travel_min > 0`, each drive between different modeled places takes that constant time. Kilometers are derived from time × average speed, so plotted line lengths are not route-distance evidence. In coordinate mode, distance is haversine × detour factor and time is distance/speed. Neither mode calls a road-network engine.

The route engine operates on aggregated sites, so the constant drive is paid between site nodes; multiple selected bins there incur multiple service times but share the drive. This is more precise than interpreting the parameter name as ten extra driving minutes for every colocated material bin.

## 7. Routing, loads, unloading and fleet recommendation

Source: [routing.py](../../Omar-Work/fillinq/routing.py).

Bin demand is capped fill fraction × container capacity, converted to liters and kilograms and summed by site. OR-Tools builds depot → candidate sites / optional reload copies → final disposal. It includes separate remaining-volume and remaining-weight dimensions; disposal copies permit replenishing available capacity. Reload copies are limited to `min(required_loads + vehicles, 30)`.

Travel and service seconds form both route cost and a shift time dimension. Site service is setup plus per-bin emptying. Reloads pay unloading time. Final unloading and disposal-to-depot travel are explicitly reserved from the shift and added back to reported totals. Each used route reports site order, map path, trips with loads, hours and bins; aggregate KPIs include trucks, trips, stops, bins, kilometers, hours, volume and weight.

Mandatory stops are technically droppable with penalty 10,000,000. Optional penalties combine site service and risk × optional-detour value. A fixed vehicle cost discourages opening trucks. Search uses parallel cheapest insertion and guided local search with a short time limit; it proposes a solution rather than proving minimum fleet/global optimality.

Fleet attempts start at an estimated work lower bound and try that count, +1, +2, +4 and configured maximum, deduplicated and clamped. Escalation stops when reported dropped-mandatory is empty. The number of used routes is the fleet recommendation, unlike Kaise's aggregate capacity formula.

## 8. Dashboard and exports

Source: [app.py](../../Omar-Work/app.py).

Seven views cover Data, Patterns, Forecast, Settings, Route planner, Backtest and Guide. Uploaded observations are cached; a model is cached per data key. Forecast charts show visit history, expected fill if not emptied, an 80% quantile band and time-to-full range. Patterns expose group CSV download.

Planning chooses a date, shows selected risks, runs routing, displays truck/trip/stop/bin/distance/hour KPIs, warns about unserved mandatory sites and visualizes truck-colored paths and optional skips. Route CSV contains per-truck/per-trip stop sequence and physical totals. Backtest pages read saved results and warn when current settings differ from stored metadata. Saved forecast/backtest metrics are not automatically recalculated for an uploaded observation file.

## 9. Evaluation and digital twin

Sources: [evaluation functions](../../Omar-Work/fillinq/forecast.py), [simulator](../../Omar-Work/fillinq/simulate.py), [runner](../../Omar-Work/run_backtest.py).

Forecast evaluation includes random five-fold cycle splits and a forward test trained on intervals ending before 1 April 2026. Baselines use material/container median rates and a mean-fill reference. MAE compares capped visit fills; AUC tests fill ≥70%, not confirmed overflow. The “always mean” comparator uses the evaluated observations' mean, so it is a retrospective reference rather than an independently fitted deployable predictor.

The twin fits a truth model on all intervals, accumulates daily seasonal rates, and gives each container/filling-cycle index a seeded log-normal multiplier. Policies share the same multiplier table, although changing collection timing changes which calendar days fall in each cycle. Both start from the last known emptying before 1 April and run through 30 September. Baseline replays visit dates; dynamic plans on configured working days with a model fitted only before April. Collection resets emptying date and advances the cycle counter; final open cycles also contribute full-days/events.

Metrics include site visits, collections, capped mean fill, low-fill share, full-at-collection share, time spent full and full-cycle events. “Overflow” in these simulation metrics is based on crossing 100, so it is not equivalent to observing the literal ground-litter `overfull` token. The runner sweeps risk thresholds and stores three routed scenarios. Routed comparisons disable optional sites with `opt_p=1.01`; the “same service” 0.82 and “same effort” 0.70 thresholds are tuned labels, not exact equality constraints.

Current [saved forecast metrics](../../Omar-Work/results/forecast_metrics.json) report random-fold MAE 16.49 pp/AUC 0.840 and chronological MAE 19.54 pp/AUC 0.785. The chronological container-median baseline is 21.31 pp/AUC 0.735. These are saved evidence, not rerun results.

Current [routed results](../../Omar-Work/results/routed_summary.csv):

| Saved simulated measure | Historical | Same service | Same effort |
| --- | ---: | ---: | ---: |
| Site visits | 2,581 | 2,081 | 2,625 |
| Container-days full | 55,814 | 54,913 | 42,587 |
| Full-cycle events | 2,478 | 2,694 | 2,580 |
| Hours | 1,211 | 1,064.33 | 1,286.83 |
| Truck-days | 217 | 194 | 217 |

The service scenario uses fewer visits/hours but more full-cycle events. The effort scenario reduces days full while using more hours. These are simulated trade-offs, not measured savings; the twin and planner share a model family and threshold tuning uses the evaluation period.

## 10. Correctness gaps and existing tests

Direct inspection identifies these material limitations:

1. The interactive dashboard fits on all intervals before the historical planning date is selected. Filtering last visits to dates before dispatch does not remove future training information. Its state also starts from the full container inventory, including future-first-observed containers.
2. `_solve` clips an individual site's liters/kg down to truck capacity, silently understating oversized demand instead of rejecting or splitting it.
3. No-solution handling returns every stop as optional and an empty mandatory list. Fleet escalation can consequently stop after failure because it sees no mandatory misses.
4. Baseline simulation empties all historically scheduled bins even when optional routing cannot serve them; dynamic simulation collects only routed sites. Served-stop accounting is asymmetric.
5. Aggregate mass/volume constraints do not enforce separate glass-color chamber limits or equipment compatibility.
6. Supplied-coordinate provenance is inferred from coverage, and bundled metrics can be displayed alongside unrelated uploads.

The [existing tests](../../Omar-Work/tests/test_core.py) exercise BOM/overflow/censoring, interval rates, bounded/monotone forecasts on synthetic data, route capacities and mandatory coverage on feasible fixtures, empty routing, fixed-drive time and Friday-to-Monday lookahead. They do not establish correctness for the failure paths above. No model fitting, solver run or test suite was executed for this documentation review.
