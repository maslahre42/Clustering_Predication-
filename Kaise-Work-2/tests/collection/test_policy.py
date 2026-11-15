"""Collection stop-selection policy tests — docs/contracts.md §3.

All scenarios use synthetic series ids ("SYNTHETIC-*") per tests/fixtures
labelling rules; no real data is read here.
"""

from __future__ import annotations

from datetime import date
from typing import get_args

import pytest

from src.collection.policy import (
    PolicyConfig,
    PolicyConfigError,
    PolicySelectionError,
    ReasonCode,
    SelectionResult,
    select_candidates,
)
from src.data.schema import MaterialType
from src.forecasting.baseline import ForecastRecord, PredictedState

AS_OF = date(2026, 8, 1)
TARGET = date(2026, 8, 29)


def make_forecast(
    location_id: str,
    material_type: MaterialType,
    predicted_fill_pct: float,
    predicted_state: PredictedState,
    as_of_date: date = AS_OF,
    target_date: date = TARGET,
) -> ForecastRecord:
    return ForecastRecord(
        location_id=location_id,
        material_type=material_type,
        as_of_date=as_of_date,
        target_date=target_date,
        predicted_fill_pct=predicted_fill_pct,
        predicted_state=predicted_state,
        method="persistence",
        horizon_days=(target_date - as_of_date).days,
    )


# ---------------------------------------------------------------------------
# PolicyConfig: defaults, validation
# ---------------------------------------------------------------------------


def test_config_defaults_match_contract() -> None:
    """Defaults 80 / 0 / True are [demo assumption] per contract §3.1."""
    config = PolicyConfig()
    assert config.select_threshold_pct == 80
    assert config.uncertainty_buffer_pct == 0
    assert config.overfull_always_selected is True


@pytest.mark.parametrize("bad_threshold", [-1, 101])
def test_config_threshold_out_of_range_raises(bad_threshold: int) -> None:
    with pytest.raises(PolicyConfigError):
        PolicyConfig(select_threshold_pct=bad_threshold)


@pytest.mark.parametrize("bad_buffer", [-1, 101])
def test_config_buffer_out_of_range_raises(bad_buffer: int) -> None:
    with pytest.raises(PolicyConfigError):
        PolicyConfig(uncertainty_buffer_pct=bad_buffer)


@pytest.mark.parametrize("bad_value", ["80", 80.0, True, None])
def test_config_non_integer_percent_raises(bad_value: object) -> None:
    """bool is excluded explicitly (True is an int subclass, not a percent)."""
    with pytest.raises(PolicyConfigError):
        PolicyConfig(select_threshold_pct=bad_value)  # type: ignore[arg-type]


def test_config_non_bool_flag_raises() -> None:
    with pytest.raises(PolicyConfigError):
        PolicyConfig(overfull_always_selected=1)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Selection rule: threshold boundary and buffer
# ---------------------------------------------------------------------------


def test_threshold_boundary_ge_selects_lt_skips() -> None:
    universe = [("SYNTHETIC-a", "brown"), ("SYNTHETIC-b", "brown")]
    forecasts = {
        ("SYNTHETIC-a", "brown"): make_forecast("SYNTHETIC-a", "brown", 80.0, "normal"),
        ("SYNTHETIC-b", "brown"): make_forecast("SYNTHETIC-b", "brown", 79.9, "normal"),
    }
    result = select_candidates(universe, forecasts, PolicyConfig())
    assert [c.location_id for c in result.selected] == ["SYNTHETIC-a"]
    assert [s.location_id for s in result.skipped] == ["SYNTHETIC-b"]
    assert result.selected[0].reason_code == "at_or_above_threshold"
    assert result.skipped[0].reason_code == "below_threshold"


def test_uncertainty_buffer_expands_selection() -> None:
    config = PolicyConfig(select_threshold_pct=80, uncertainty_buffer_pct=10)
    universe = [("SYNTHETIC-a", "brown"), ("SYNTHETIC-b", "brown")]
    forecasts = {
        ("SYNTHETIC-a", "brown"): make_forecast("SYNTHETIC-a", "brown", 70.0, "normal"),
        ("SYNTHETIC-b", "brown"): make_forecast("SYNTHETIC-b", "brown", 69.9, "normal"),
    }
    result = select_candidates(universe, forecasts, config)
    # 70 + 10 >= 80 selects; 69.9 + 10 = 79.9 < 80 skips.
    assert [c.location_id for c in result.selected] == ["SYNTHETIC-a"]
    assert [s.location_id for s in result.skipped] == ["SYNTHETIC-b"]
    assert "buffer 10" in result.selected[0].detail


# ---------------------------------------------------------------------------
# Selection rule: overfull state
# ---------------------------------------------------------------------------


def test_overfull_always_selected_on_selects_below_threshold() -> None:
    """overfull token is never coerced; numeric fallback 40 is below threshold
    yet the overfull policy selects it (contract §3.2)."""
    config = PolicyConfig(select_threshold_pct=80, overfull_always_selected=True)
    forecasts = {("SYNTHETIC-o", "green"): make_forecast("SYNTHETIC-o", "green", 40.0, "overfull")}
    result = select_candidates([("SYNTHETIC-o", "green")], forecasts, config)
    assert [c.location_id for c in result.selected] == ["SYNTHETIC-o"]
    assert result.selected[0].reason_code == "overfull_state"
    assert result.skipped == []


def test_overfull_always_selected_off_falls_back_to_threshold() -> None:
    """With the policy off, the overfull series is judged on numbers only."""
    config = PolicyConfig(select_threshold_pct=80, overfull_always_selected=False)
    below = make_forecast("SYNTHETIC-o", "green", 40.0, "overfull")
    above = make_forecast("SYNTHETIC-p", "green", 95.0, "overfull")
    result = select_candidates(
        [("SYNTHETIC-o", "green"), ("SYNTHETIC-p", "green")],
        {("SYNTHETIC-o", "green"): below, ("SYNTHETIC-p", "green"): above},
        config,
    )
    assert [s.location_id for s in result.skipped] == ["SYNTHETIC-o"]
    assert result.skipped[0].reason_code == "below_threshold"
    # Selected by numbers; reason reflects the deciding rule, not the state.
    assert [c.location_id for c in result.selected] == ["SYNTHETIC-p"]
    assert result.selected[0].reason_code == "at_or_above_threshold"


def test_overfull_rule_takes_precedence_in_reason_code() -> None:
    """When both rules select, the overfull override is the deciding cause."""
    config = PolicyConfig(overfull_always_selected=True)
    forecasts = {("SYNTHETIC-o", "white"): make_forecast("SYNTHETIC-o", "white", 92.0, "overfull")}
    result = select_candidates([("SYNTHETIC-o", "white")], forecasts, config)
    assert result.selected[0].reason_code == "overfull_state"


# ---------------------------------------------------------------------------
# no_forecast skip
# ---------------------------------------------------------------------------


def test_series_without_forecast_is_skipped_with_no_forecast() -> None:
    """Universe series with no forecast (e.g. persistence None on overfull-only
    history) ⇒ Skip with predicted_* None (contract §3.4)."""
    forecasts = {("SYNTHETIC-a", "brown"): make_forecast("SYNTHETIC-a", "brown", 90.0, "normal")}
    universe = [("SYNTHETIC-a", "brown"), ("SYNTHETIC-b", "green")]
    result = select_candidates(universe, forecasts, PolicyConfig())
    assert len(result.skipped) == 1
    skip = result.skipped[0]
    assert (skip.location_id, skip.material_type) == ("SYNTHETIC-b", "green")
    assert skip.predicted_fill_pct is None
    assert skip.predicted_state is None
    assert skip.reason_code == "no_forecast"
    assert [c.location_id for c in result.selected] == ["SYNTHETIC-a"]


# ---------------------------------------------------------------------------
# Errors: batch vs universe, mixed dates
# ---------------------------------------------------------------------------


def test_forecast_key_not_in_universe_raises() -> None:
    forecasts = {("SYNTHETIC-x", "brown"): make_forecast("SYNTHETIC-x", "brown", 90.0, "normal")}
    with pytest.raises(PolicySelectionError, match="not in universe"):
        select_candidates([("SYNTHETIC-a", "brown")], forecasts, PolicyConfig())


def test_mixed_as_of_dates_raise() -> None:
    other = make_forecast("SYNTHETIC-b", "brown", 90.0, "normal", as_of_date=date(2026, 7, 1))
    forecasts = {
        ("SYNTHETIC-a", "brown"): make_forecast("SYNTHETIC-a", "brown", 90.0, "normal"),
        ("SYNTHETIC-b", "brown"): other,
    }
    with pytest.raises(PolicySelectionError, match="as_of_date"):
        select_candidates(
            [("SYNTHETIC-a", "brown"), ("SYNTHETIC-b", "brown")], forecasts, PolicyConfig()
        )


def test_mixed_target_dates_raise() -> None:
    other = make_forecast("SYNTHETIC-b", "brown", 90.0, "normal", target_date=date(2026, 9, 5))
    forecasts = {
        ("SYNTHETIC-a", "brown"): make_forecast("SYNTHETIC-a", "brown", 90.0, "normal"),
        ("SYNTHETIC-b", "brown"): other,
    }
    with pytest.raises(PolicySelectionError, match="target_date"):
        select_candidates(
            [("SYNTHETIC-a", "brown"), ("SYNTHETIC-b", "brown")], forecasts, PolicyConfig()
        )


def test_duplicate_universe_key_raises() -> None:
    """Duplicate universe entries would break the exactly-once invariant."""
    forecasts = {("SYNTHETIC-a", "brown"): make_forecast("SYNTHETIC-a", "brown", 90.0, "normal")}
    universe = [("SYNTHETIC-a", "brown"), ("SYNTHETIC-a", "brown")]
    with pytest.raises(PolicySelectionError, match="duplicate"):
        select_candidates(universe, forecasts, PolicyConfig())


def test_forecast_with_empty_universe_raises() -> None:
    forecasts = {("SYNTHETIC-a", "brown"): make_forecast("SYNTHETIC-a", "brown", 90.0, "normal")}
    with pytest.raises(PolicySelectionError, match="not in universe"):
        select_candidates([], forecasts, PolicyConfig())


# ---------------------------------------------------------------------------
# Empty universe
# ---------------------------------------------------------------------------


def test_empty_universe_yields_empty_result_with_none_dates() -> None:
    result = select_candidates([], {}, PolicyConfig())
    assert isinstance(result, SelectionResult)
    assert result.as_of_date is None
    assert result.target_date is None
    assert result.selected == []
    assert result.skipped == []
    assert result.config == PolicyConfig()


# ---------------------------------------------------------------------------
# Result shape: dates, ordering, invariants, detail
# ---------------------------------------------------------------------------


def test_result_dates_echo_batch() -> None:
    forecasts = {("SYNTHETIC-a", "brown"): make_forecast("SYNTHETIC-a", "brown", 90.0, "normal")}
    result = select_candidates([("SYNTHETIC-a", "brown")], forecasts, PolicyConfig())
    assert result.as_of_date == AS_OF
    assert result.target_date == TARGET


def test_selected_order_fill_desc_then_key() -> None:
    universe = [
        ("SYNTHETIC-b", "green"),
        ("SYNTHETIC-a", "green"),
        ("SYNTHETIC-a", "brown"),
        ("SYNTHETIC-c", "brown"),
    ]
    fills: dict[tuple[str, MaterialType], float] = {
        ("SYNTHETIC-b", "green"): 90.0,
        ("SYNTHETIC-a", "green"): 95.0,
        ("SYNTHETIC-a", "brown"): 90.0,
        ("SYNTHETIC-c", "brown"): 99.0,
    }
    forecasts = {key: make_forecast(key[0], key[1], fill, "normal") for key, fill in fills.items()}
    result = select_candidates(universe, forecasts, PolicyConfig())
    assert [(c.location_id, c.material_type) for c in result.selected] == [
        ("SYNTHETIC-c", "brown"),  # 99.0
        ("SYNTHETIC-a", "green"),  # 95.0
        ("SYNTHETIC-a", "brown"),  # 90.0 (tie: key order)
        ("SYNTHETIC-b", "green"),  # 90.0
    ]


def test_skipped_order_by_key() -> None:
    universe = [("SYNTHETIC-c", "white"), ("SYNTHETIC-a", "green"), ("SYNTHETIC-b", "brown")]
    forecasts = {
        ("SYNTHETIC-a", "green"): make_forecast("SYNTHETIC-a", "green", 10.0, "normal"),
        ("SYNTHETIC-b", "brown"): make_forecast("SYNTHETIC-b", "brown", 20.0, "normal"),
        ("SYNTHETIC-c", "white"): make_forecast("SYNTHETIC-c", "white", 30.0, "normal"),
    }
    result = select_candidates(universe, forecasts, PolicyConfig())
    assert [(s.location_id, s.material_type) for s in result.skipped] == [
        ("SYNTHETIC-a", "green"),
        ("SYNTHETIC-b", "brown"),
        ("SYNTHETIC-c", "white"),
    ]


def test_every_universe_series_appears_exactly_once() -> None:
    universe = [
        ("SYNTHETIC-a", "brown"),
        ("SYNTHETIC-b", "green"),
        ("SYNTHETIC-c", "white"),
    ]
    forecasts = {
        ("SYNTHETIC-a", "brown"): make_forecast("SYNTHETIC-a", "brown", 90.0, "normal"),
        # SYNTHETIC-b has a forecast; SYNTHETIC-c does not.
        ("SYNTHETIC-b", "green"): make_forecast("SYNTHETIC-b", "green", 20.0, "normal"),
    }
    result = select_candidates(universe, forecasts, PolicyConfig())
    covered = [(c.location_id, c.material_type) for c in result.selected] + [
        (s.location_id, s.material_type) for s in result.skipped
    ]
    assert sorted(covered) == sorted(universe)
    assert len(covered) == len(set(covered))


def test_detail_contains_deciding_numbers_contract_example() -> None:
    forecasts = {("SYNTHETIC-a", "brown"): make_forecast("SYNTHETIC-a", "brown", 92.0, "normal")}
    result = select_candidates([("SYNTHETIC-a", "brown")], forecasts, PolicyConfig())
    assert result.selected[0].detail == "predicted 92.0 >= threshold 80 + buffer 0"


def test_below_threshold_detail_contains_numbers() -> None:
    forecasts = {("SYNTHETIC-a", "brown"): make_forecast("SYNTHETIC-a", "brown", 55.5, "normal")}
    result = select_candidates([("SYNTHETIC-a", "brown")], forecasts, PolicyConfig())
    assert result.skipped[0].detail == "predicted 55.5 < threshold 80 + buffer 0"


# ---------------------------------------------------------------------------
# Determinism and reason-code enum
# ---------------------------------------------------------------------------


def test_deterministic_same_inputs_same_output() -> None:
    universe = [("SYNTHETIC-a", "brown"), ("SYNTHETIC-b", "green"), ("SYNTHETIC-c", "white")]
    forecasts = {
        ("SYNTHETIC-a", "brown"): make_forecast("SYNTHETIC-a", "brown", 90.0, "normal"),
        ("SYNTHETIC-b", "green"): make_forecast("SYNTHETIC-b", "green", 85.0, "full"),
        # SYNTHETIC-c: no forecast → no_forecast skip.
    }
    first = select_candidates(universe, forecasts, PolicyConfig())
    second = select_candidates(
        reversed(universe), dict(reversed(list(forecasts.items()))), PolicyConfig()
    )
    assert first == second


def test_reason_codes_are_the_exact_contract_enum() -> None:
    assert set(get_args(ReasonCode)) == {
        "at_or_above_threshold",
        "overfull_state",
        "below_threshold",
        "no_forecast",
    }
