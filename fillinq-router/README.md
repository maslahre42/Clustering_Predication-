## WasteRouting.AI: from fill-level readings to routes

Prototype for the Future City Hackathon 2026 (PreZero challenge). It turns irregular glass-container
fill-level readings into (1) pattern insights, (2) a forecast of when each container overflows,
(3) a configurable route planner that decides which sites to visit and how many trucks to send, and
(4) a backtest that compares it with the historical fixed schedule.

### Quick start

```bash
pip install -r requirements.txt
python run_backtest.py          # once, about 10 minutes (use --fast to skip routing, about 2 minutes)
streamlit run app.py
```

The app opens with the bundled PreZero file. You can upload another CSV with the same columns
(`Location_id, material_type, date, fill_level_perc`) and an optional site-location CSV
(`site, lat, lon`) in the sidebar.

### How it works

```
CSV upload -> data.py (clean, censored readings, filling cycles)
           -> patterns.py (monthly/weekday/material patterns, site groups)
           -> forecast.py (fill-rate model: container + season + vacation, censored likelihood)
           -> policy.py   (which bins are at risk? mandatory vs. optional stops)
           -> routing.py  (OR-Tools: capacity in volume AND weight, shift, multi-trip, fleet size)
           -> simulate.py (digital twin, historical schedule vs. dynamic policy)
           -> app.py      (Streamlit dashboard)
```

**Forecast model.** A filling cycle is the time between two readings of a container. Its daily fill rate is
log-normal with a container effect (shrunk towards the glass-type average, so containers with few readings
borrow strength), a month effect and a school-vacation effect. Readings of 100% or "overfull" are treated as
*at least* 100%, not as exact values. From the model we get the expected fill and the probability of
overflow for any day after the last emptying. Estimation is by maximum a-posteriori with an analytic gradient
and takes about a second.

**Route engine.** Containers whose overflow probability within the look-ahead window is above a threshold
make their site a *mandatory* stop. Other risky sites are *optional* and are visited only if the detour is
cheaper than their value (prize-collecting vehicle routing). Trucks have a volume and a weight limit and a
shift length. When full they drive to the disposal site and continue (multi-trip). Each route ends with a final
unload and the drive to the depot. A fixed cost per truck makes the solver use as few trucks as possible, so
the number of trucks used is the **fleet recommendation**.

**Configurable variables** (sidebar of the route planner, defaults in `fillinq/config.py`): glass density,
container volume, truck volume and payload, number of trucks, shift length, speed, minutes per stop and per
container, unloading time, depot and disposal location, look-ahead and risk threshold.

### Backtest

The twin generates the true fill of every container (model fitted on all data, a random multiplier per filling
cycle, same random numbers for every policy). The *historical schedule* replays the real visit calendar. The
*dynamic* policy plans every weekday using only the date each container was last emptied and a model trained
on data up to 31 March. Both are scored on the same true fill levels from 1 April to 30 September.

Honest limits: the twin shares its structure with the forecast, and readings exist only at visits. Treat
absolute numbers as indicative. Dynamic collection reduces the time containers sit full and the wasted
half-empty visits; it does not eliminate overflow events, because single filling cycles are unpredictable
without live sensors.

### Results (April to September 2026, planner trained on data up to March)

| | Historical schedule | Dynamic, same service | Dynamic, same effort |
|---|---|---|---|
| Site visits | 2,581 | **1,993 (-23%)** | 2,682 (+4%) |
| Container-days spent full | 55.8k | 56.3k (+1%) | **42.0k (-25%)** |
| Mean fill at collection | 64% | 74% | 67% |
| Collections below 40% full | 31% | **20%** | 26% |
| Truck-days | 336 | **251 (-25%)** | 297 (-12%) |
| Working hours (illustrative) | 1,179 | 1,118 (-5%) | 1,351 (+15%) |
| Distance in km (illustrative) | 12,205 | 12,523 (+3%) | 14,474 (+19%) |
| Overflow events | 2,478 | 2,704 | 2,590 |

Forecast quality on held-out readings: AUC 0.84 for "needs collection (fill >= 70%)", against 0.56 when only
the time since the last visit is known (what a fixed schedule effectively knows). Average error of predicted
fill 16.5 points against 26.5 for guessing the mean.

Read with care: distance and hours use synthetic coordinates, so do not claim kilometre savings until real
locations are in (dynamic stops are spread thinly across days, so distance per stop rises). The robust
findings are fewer visits, fewer truck-days, less time containers sit full, and fewer wasted half-empty
visits. The number of overflow events does not fall, because single filling cycles are unpredictable
without live sensors.

### Assumptions to confirm with PreZero

1. A reading is taken **before** the container is emptied, and it is emptied at that visit.
2. Container volume, glass density, truck volume and payload, depot and disposal location are
   **placeholders** in `config.py`.
3. The file has **no coordinates**. Positions are synthetic (spread over Heilbronn districts) until you add
   `data/site_locations.csv`. Stop counts, fill levels and overflow results do not depend on them;
   kilometres and hours do. Road distance is straight-line times 1.3 (swap in OSRM or OpenRouteService later).
4. School vacation dates are Baden-Württemberg 2025/26 (`fillinq/calendar_features.py`); holidays come from the
   `holidays` package.

### Ideas for next steps

Update container rates online from every new reading; use weather and local events as forecast inputs;
real road distances; a driver app that writes the observed fill level back (closing the loop); other waste
streams by changing density and container size.

### Tests

`pytest -q`
