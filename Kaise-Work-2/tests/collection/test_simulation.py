"""Strategy simulation core tests (v4) — docs/contracts.md §5.2.4/§5.2.5.

Hand-computed tiny fixtures (1-2 series with known rates); every expected
number is derived in the test docstring. All parameter values are [demo
assumption]/[representative] test arithmetic, never real-world claims.

Replay initialisation (§5.2.5 v4 addendum): every call passes the required
``prior_emptying_dates`` mapping (series key → pre-window emptying date ≤
start_date); the §5.2.3 ``last_emptying_date`` never seeds the clock.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.collection.simulation import (
    STRATEGY_DEMAND_DRIVEN,
    STRATEGY_FIXED_FREQUENCY,
    Calibration,
    SimulationConfig,
    SimulationConfigError,
    calibration,
    observed_anchor,
    simulate_strategy,
)
from src.data.schema import MaterialType, ReadingRecord
from src.forecasting.days_to_full import SeriesDaysToFull

START = date(2026, 1, 1)
LAST_EMPTYING = date(2026, 1, 1)


def estimate(
    location_id: str,
    rate: float | None,
    material_type: MaterialType = "brown",
    reason: str | None = None,
    last_emptying_date: date = LAST_EMPTYING,
) -> SeriesDaysToFull:
    """A §5.2.3 row with only the fields the simulation core consumes.
    ``last_emptying_date`` is a §5.2.3 response field only — the replay
    clock is seeded by the ``prior_emptying_dates`` mapping (§5.2.5 v4
    addendum), never by this field."""
    return SeriesDaysToFull(
        location_id=location_id,
        material_type=material_type,
        last_emptying_date=last_emptying_date,
        last_fill_pct=None if reason else 50,
        last_is_overfull=False,
        rate_pct_per_day=rate,
        median_interval_days=None,
        days_to_full=None,
        predicted_full_date=None,
        is_lower_bound=False,
        reason=reason,  # type: ignore[arg-type]
    )


def reading(fill: int | None, is_overfull: bool = False) -> ReadingRecord:
    return ReadingRecord(
        location_id="loc-x",
        material_type="brown",
        date=START,
        fill_level_pct=fill,
        is_overfull=is_overfull,
    )


# ---------------------------------------------------------------------------
# fixed_frequency k-day cycle
# ---------------------------------------------------------------------------


def test_fixed_frequency_empties_on_the_k_day_cycle() -> None:
    """Rates 2 %/day (loc-a) and 3 %/day (loc-b), prior emptyings exactly ==
    start (2026-01-01 — the valid == boundary: emptied on day 0, so due
    again at start + frequency_days), window 2026-01-01..01-29 (29 days),
    frequency 28: both series are due on 01-29 (28 days elapsed; 01-28 has
    only 27). Fills at emptying: 2 x 28 = 56 % and 3 x 28 = 84 % — below
    100, so no overfull emptyings and no overflow. Max end-of-day fill is
    01-28: 3 x 27 = 81 %."""
    config = SimulationConfig(frequency_days=28)
    result = simulate_strategy(
        [estimate("loc-a", 2.0), estimate("loc-b", 3.0, material_type="green")],
        STRATEGY_FIXED_FREQUENCY,
        config,
        START,
        date(2026, 1, 29),
        prior_emptying_dates={
            ("loc-a", "brown"): START,
            ("loc-b", "green"): START,
        },
    )

    assert result.stops_total == 2
    assert [record.collections for record in result.days] == [0] * 28 + [2]
    assert result.days[-1].date == date(2026, 1, 29)
    assert result.fills_at_emptying == [56.0, 84.0]  # (location_id, material) order
    assert result.service.share_emptyings_full_or_overfull_pct == 0.0
    assert result.service.overflow_share_pct == 0.0
    assert result.service.max_fill_pct == 81.0
    assert result.skipped == []


def test_fixed_frequency_repeats_the_cycle_after_emptying() -> None:
    """One 7 %/day series, frequency 14, prior emptying == start (2026-01-01,
    day 0), window 2026-01-01..02-11 (42 days): due when days_since >= 14 —
    on 01-15 (14 days after 01-01), then 14 days later on 01-29; 02-12 would
    be next and is outside the window. Fill at emptying: 7 x 14 = 98 % each
    time (never >= 100). Max END-OF-DAY fill: 01-28, 13 days after the
    01-15 emptying — 7 x 13 = 91 % (98 % exists only at the 01-29 emptying
    moment; that day ends at 0)."""
    config = SimulationConfig(frequency_days=14)
    result = simulate_strategy(
        [estimate("loc-a", 7.0)],
        STRATEGY_FIXED_FREQUENCY,
        config,
        START,
        date(2026, 2, 11),
        prior_emptying_dates={("loc-a", "brown"): START},
    )

    assert result.stops_total == 2
    collection_days = [record.date for record in result.days if record.collections == 1]
    assert collection_days == [date(2026, 1, 15), date(2026, 1, 29)]
    assert result.fills_at_emptying == [98.0, 98.0]
    assert result.service.max_fill_pct == 91.0
    assert result.service.overflow_share_pct == 0.0


# ---------------------------------------------------------------------------
# demand_driven threshold
# ---------------------------------------------------------------------------


def test_demand_driven_triggers_at_the_threshold_inclusively() -> None:
    """5 %/day series, threshold 80, prior emptying == start (day 0, fill 0):
    fill >= 80 at 16 days elapsed, i.e. the first emptying is 2026-01-17
    with fill exactly 80 (inclusive boundary). The next threshold day would
    be 17 + 16 = 02-02 — outside the window ending 01-31, so exactly one
    emptying."""
    config = SimulationConfig(select_threshold_pct=80.0)
    result = simulate_strategy(
        [estimate("loc-a", 5.0)],
        STRATEGY_DEMAND_DRIVEN,
        config,
        START,
        date(2026, 1, 31),
        prior_emptying_dates={("loc-a", "brown"): START},
    )

    assert result.stops_total == 1
    assert [record.collections for record in result.days] == [0] * 16 + [1] + [0] * 14
    assert result.days[16].date == date(2026, 1, 17)
    assert result.fills_at_emptying == [80.0]
    assert result.service.share_emptyings_full_or_overfull_pct == 0.0


def test_demand_driven_empties_an_already_overfull_series_on_day_one() -> None:
    """Rate 5 %/day, prior emptying 2025-12-01 via prior_emptying_dates
    (31 days before the window start: 01-01 - 12-01 = 31): fill at
    2026-01-01 is 5 x 31 = 155 % — >= 80 (and >= 100), so the series
    empties on day one and the emptying counts as full/overfull. Collection
    is capped at the container volume (100 %); the end-of-day fill is 5 %,
    so no overflow that day."""
    config = SimulationConfig(select_threshold_pct=80.0)
    result = simulate_strategy(
        [estimate("loc-a", 5.0)],
        STRATEGY_DEMAND_DRIVEN,
        config,
        START,
        date(2026, 1, 3),
        prior_emptying_dates={("loc-a", "brown"): date(2025, 12, 1)},
    )

    assert result.stops_total == 1
    assert result.fills_at_emptying == [155.0]
    assert result.service.share_emptyings_full_or_overfull_pct == 100.0
    assert result.days[0].collections == 1
    assert result.days[0].overflow_containers == 0


# ---------------------------------------------------------------------------
# overflow counting
# ---------------------------------------------------------------------------


def test_overflow_counts_container_days_above_100() -> None:
    """10 %/day series, fixed frequency 28, prior emptying == start (day 0),
    window 2026-01-01..01-29: fill > 100 from 01-12 (110 %) through 01-28
    (270 %) — 17 container-days; on 01-29 the series is emptied (fill
    280 >= 100, an overfull emptying) and the end-of-day fill is 0.
    Container-days total 29, so the overflow share is
    round(100 x 17 / 29, 1) = 58.6."""
    config = SimulationConfig(frequency_days=28)
    result = simulate_strategy(
        [estimate("loc-a", 10.0)],
        STRATEGY_FIXED_FREQUENCY,
        config,
        START,
        date(2026, 1, 29),
        prior_emptying_dates={("loc-a", "brown"): START},
    )

    assert [record.overflow_containers for record in result.days] == [0] * 11 + [1] * 17 + [0]
    assert result.service.overflow_share_pct == 58.6
    assert result.service.share_emptyings_full_or_overfull_pct == 100.0
    assert result.service.max_fill_pct == 270.0


# ---------------------------------------------------------------------------
# truck-day arithmetic (disposal unload, then shift split)
# ---------------------------------------------------------------------------


def test_disposal_unload_keeps_one_full_truck_on_the_route() -> None:
    """Two brown stops at 100 % x 3,000 L = 3,000 L / 1,200 kg each on one
    day (prior emptyings 2025-12-24, 8 days before the window: fill =
    (100/8) x 8 = 100 % on 2026-01-01; §4.6 truck: 4,000 L brown
    compartment, 10,000 kg, 480 min shift, 10 min legs, 5 min service,
    30 min disposal): truck 1 loads stop 1
    (15 min); stop 2 would make 6,000 > 4,000 L, so the truck unloads at
    disposal (10 + 30 + 10 = 50 min) and loads stop 2 — day total
    15 + 50 + 15 = 80 <= 480. Expected: ONE truck-day despite the capacity
    split ("disposal every full vehicle")."""
    config = SimulationConfig(frequency_days=8)
    result = simulate_strategy(
        [estimate("loc-a", 100.0 / 8), estimate("loc-b", 100.0 / 8)],
        STRATEGY_FIXED_FREQUENCY,
        config,
        START,
        date(2026, 1, 1),
        prior_emptying_dates={
            ("loc-a", "brown"): date(2025, 12, 24),
            ("loc-b", "brown"): date(2025, 12, 24),
        },
    )

    assert result.days[0].collections == 2
    assert result.days[0].truck_days == 1
    assert result.truck_days == 1
    assert result.cost_eur_total == 500.0


def test_shift_limit_splits_the_day_across_trucks() -> None:
    """Two brown stops at 40 % x 3,000 L = 1,200 L / 480 kg each on one day
    (prior emptyings 2025-12-24, 8 days before the window: fill =
    (40/8) x 8 = 40 %), weight capacity 900 kg, shift 60 min: truck 1 loads
    stop 1 (15 min, 480 <= 900 kg); stop 2 would reach 960 > 900 kg, so the
    truck unloads at disposal (10 + 30 + 10 = 50 min, cumulative 65) and the
    day would end at 65 + 15 = 80 > 60 min shift — the stop moves to truck 2
    (15 min). Expected: 2 truck-days, 2 x 500 = 1,000 EUR."""
    config = SimulationConfig(
        frequency_days=8,
        weight_capacity_kg=900,
        max_shift_minutes=60,
        cost_per_truck_day_eur=500.0,
    )
    result = simulate_strategy(
        [estimate("loc-a", 40.0 / 8), estimate("loc-b", 40.0 / 8)],
        STRATEGY_FIXED_FREQUENCY,
        config,
        START,
        date(2026, 1, 1),
        prior_emptying_dates={
            ("loc-a", "brown"): date(2025, 12, 24),
            ("loc-b", "brown"): date(2025, 12, 24),
        },
    )

    assert result.days[0].collections == 2
    assert result.days[0].truck_days == 2
    assert result.truck_days == 2
    assert result.cost_eur_total == 1000.0
    assert result.days[0].cumulative_cost_eur == 1000.0
    assert result.fills_at_emptying == [40.0, 40.0]


def test_truck_day_is_zero_on_days_without_collections() -> None:
    config = SimulationConfig(frequency_days=28)
    result = simulate_strategy(
        [estimate("loc-a", 2.0)],
        STRATEGY_FIXED_FREQUENCY,
        config,
        START,
        date(2026, 1, 5),
        prior_emptying_dates={("loc-a", "brown"): START},
    )
    assert all(record.truck_days == 0 for record in result.days)
    assert result.truck_days == 0
    assert result.cost_eur_total == 0.0


# ---------------------------------------------------------------------------
# costs ([predicted] derivations)
# ---------------------------------------------------------------------------


def test_cost_eur_per_year_scales_the_window_proportionally() -> None:
    """[predicted] derivation: (truck_days / replay_days) x rate x
    operating_days_per_year = 1/29 x 500 x 200 = 3,448.28 EUR."""
    config = SimulationConfig(frequency_days=28)
    result = simulate_strategy(
        [estimate("loc-a", 2.0)],
        STRATEGY_FIXED_FREQUENCY,
        config,
        START,
        date(2026, 1, 29),
        prior_emptying_dates={("loc-a", "brown"): START},
    )
    assert result.cost_eur_total == 500.0
    assert result.cost_eur_per_year == round(500.0 / 29 * 200, 2)


def test_cumulative_cost_accumulates_over_collection_days() -> None:
    """10 %/day series, frequency 3: due at days_since >= 3 — on 01-04,
    then 01-07 (01-10 is outside the window ending 01-09). Cumulative cost
    rises by 500 on each collection day and holds otherwise."""
    config = SimulationConfig(frequency_days=3)
    result = simulate_strategy(
        [estimate("loc-a", 10.0)],
        STRATEGY_FIXED_FREQUENCY,
        config,
        START,
        date(2026, 1, 9),
        prior_emptying_dates={("loc-a", "brown"): START},
    )
    costs = [record.cumulative_cost_eur for record in result.days]
    assert costs == [0.0, 0.0, 0.0, 500.0, 500.0, 500.0, 1000.0, 1000.0, 1000.0]
    assert result.truck_days == 2
    assert result.cost_eur_total == 1000.0


# ---------------------------------------------------------------------------
# skipped series (no usable rate) — counted, never fabricated
# ---------------------------------------------------------------------------


def test_series_without_usable_rate_are_skipped_with_reason() -> None:
    config = SimulationConfig(frequency_days=28)
    result = simulate_strategy(
        [
            estimate("loc-zero", 0.0, reason="zero_rate"),
            estimate("loc-none", None, reason="not_enough_records"),
            estimate("loc-ok", 2.0),
        ],
        STRATEGY_FIXED_FREQUENCY,
        config,
        START,
        date(2026, 1, 29),
        prior_emptying_dates={("loc-ok", "brown"): START},
    )

    assert result.stops_total == 1  # only loc-ok is simulated
    assert [(skip.location_id, skip.reason) for skip in result.skipped] == [
        ("loc-none", "not_enough_records"),
        ("loc-zero", "zero_rate"),
    ]


# ---------------------------------------------------------------------------
# determinism + input validation
# ---------------------------------------------------------------------------


def test_two_runs_are_identical() -> None:
    config = SimulationConfig(frequency_days=14)
    series = [estimate("loc-a", 5.0), estimate("loc-b", 3.0, material_type="green")]
    priors = {("loc-a", "brown"): START, ("loc-b", "green"): START}
    first = simulate_strategy(
        series,
        STRATEGY_FIXED_FREQUENCY,
        config,
        START,
        date(2026, 2, 11),
        prior_emptying_dates=priors,
    )
    second = simulate_strategy(
        series,
        STRATEGY_FIXED_FREQUENCY,
        config,
        START,
        date(2026, 2, 11),
        prior_emptying_dates=priors,
    )
    assert first == second


def test_invalid_inputs_raise() -> None:
    config = SimulationConfig(frequency_days=28)
    with pytest.raises(ValueError, match="before start_date"):
        simulate_strategy(
            [], STRATEGY_FIXED_FREQUENCY, config, START, date(2025, 12, 31), prior_emptying_dates={}
        )
    with pytest.raises(ValueError, match="strategy"):
        simulate_strategy(
            [],
            "cheapest",
            config,
            START,
            date(2026, 1, 2),
            prior_emptying_dates={},  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# replay initialisation (§5.2.5 v4 addendum): prior_emptying_dates
# ---------------------------------------------------------------------------


def test_prior_emptying_date_after_start_date_raises() -> None:
    """A mapped date > start_date is an honest SimulationConfigError — never
    a silent clamp. (A date exactly == start_date is valid — see the k-day
    cycle test: emptied on day 0, due again at start + frequency_days.)"""
    config = SimulationConfig(frequency_days=7)
    with pytest.raises(SimulationConfigError, match="prior_emptying_dates must be ≤ start_date"):
        simulate_strategy(
            [estimate("loc-a", 5.0)],
            STRATEGY_FIXED_FREQUENCY,
            config,
            START,
            date(2026, 1, 3),
            prior_emptying_dates={("loc-a", "brown"): date(2026, 1, 2)},
        )


def test_last_emptying_date_never_seeds_the_clock() -> None:
    """Rate 10 %/day, prior emptying 2025-12-27 (5 days before the window:
    01-01 - 12-27 = 5): fill at 2026-01-01 is 10 x 5 = 50 %; due at
    days_since >= 10 → 2026-01-06 with fill 10 x 10 = 100 % (a full
    emptying); max END-OF-DAY fill is 01-05, 9 days after the prior
    emptying — 10 x 9 = 90 %. The §5.2.3 last_emptying_date 2026-06-30 lies
    AFTER the window: if it still seeded the clock, every days_since would
    be negative, fill pinned at 0 and stops_total would be 0, not 1."""
    config = SimulationConfig(frequency_days=10)
    result = simulate_strategy(
        [estimate("loc-a", 10.0, last_emptying_date=date(2026, 6, 30))],
        STRATEGY_FIXED_FREQUENCY,
        config,
        START,
        date(2026, 1, 10),
        prior_emptying_dates={("loc-a", "brown"): date(2025, 12, 27)},
    )

    assert result.stops_total == 1
    collection_days = [record.date for record in result.days if record.collections == 1]
    assert collection_days == [date(2026, 1, 6)]
    assert result.fills_at_emptying == [100.0]
    assert result.service.share_emptyings_full_or_overfull_pct == 100.0
    assert result.service.max_fill_pct == 90.0


def test_series_without_mapping_entry_starts_empty_at_start_date() -> None:
    """No prior entry → the clock starts at start_date (fill 0 on day 0).
    Rate 10 %/day, frequency 3, window 2026-01-01..01-04: due at
    days_since >= 3 → 01-04 only (fill 10 x 3 = 30 %)."""
    config = SimulationConfig(frequency_days=3)
    result = simulate_strategy(
        [estimate("loc-a", 10.0)],
        STRATEGY_FIXED_FREQUENCY,
        config,
        START,
        date(2026, 1, 4),
        prior_emptying_dates={},
    )

    assert [record.collections for record in result.days] == [0, 0, 0, 1]
    assert result.fills_at_emptying == [30.0]


def test_simulation_config_validates_parameters() -> None:
    for kwargs in (
        {"frequency_days": 0},
        {"frequency_days": True},
        {"select_threshold_pct": 101},
        {"select_threshold_pct": -1},
        {"select_threshold_pct": 0},  # 0 is allowed by §3.1 bounds
        {"cost_per_truck_day_eur": 0},
        {"containers_per_series": 0},
        {"operating_days_per_year": 0},
        {"operating_days_per_year": 367},
    ):
        if kwargs == {"select_threshold_pct": 0}:
            continue  # valid boundary — asserted below
        with pytest.raises(SimulationConfigError):
            SimulationConfig(**kwargs)  # type: ignore[arg-type]
    assert SimulationConfig(select_threshold_pct=0).select_threshold_pct == 0


# ---------------------------------------------------------------------------
# observed anchor + calibration (§5.2.4/§5.2.5)
# ---------------------------------------------------------------------------


def test_observed_anchor_counts_overfull_and_numeric_full() -> None:
    records = [
        reading(100),
        reading(None, is_overfull=True),
        reading(45),
        reading(100),
    ]
    anchor = observed_anchor(records)
    assert anchor.basis == "observed_emptying_records"
    assert anchor.share_full_or_overfull_pct == 75.0  # 3 of 4
    assert anchor.max_fill_pct == 100.0


def test_observed_anchor_empty_records_give_none_values() -> None:
    anchor = observed_anchor([])
    assert anchor.share_full_or_overfull_pct is None
    assert anchor.max_fill_pct is None


def test_calibration_medians_pair() -> None:
    result = calibration(
        [50.0, 90.0, 140.0],
        [reading(100), reading(45), reading(None, is_overfull=True)],
    )
    assert isinstance(result, Calibration)
    assert result.simulated_fill_at_emptying_median_pct == 90.0
    assert result.observed_fill_at_emptying_median_pct == 72.5  # median(100, 45)


def test_calibration_with_empty_sides_gives_none() -> None:
    result = calibration([], [reading(30)])
    assert result.simulated_fill_at_emptying_median_pct is None
    assert result.observed_fill_at_emptying_median_pct == 30.0
