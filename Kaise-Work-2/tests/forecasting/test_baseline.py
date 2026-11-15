"""Baseline tests — hand-computed persistence/rate behaviour (contract §2.3).

v4 rate semantics: expected fill at the next emptying = §1.5 accumulation
rate x the series' median observed interval, clipped to [0, 100]. No usable
rate ⇒ no numeric prediction (None) — never a persistence fallback and never
a default rate.
"""

from __future__ import annotations

from datetime import date

from src.data.schema import MaterialType
from src.forecasting.baseline import forecast, forecast_persistence, forecast_rate
from src.forecasting.features import FeatureRow
from src.forecasting.targets import EvaluationCase, build_evaluation_cases


def make_case(
    features: FeatureRow,
    horizon_days: int = 30,
    truth_fill_pct: int | None = 50,
) -> EvaluationCase:
    return EvaluationCase(
        location_id="SYNTHETIC-f-x",
        material_type="brown",
        as_of_date=date(2026, 1, 1),
        target_date=date(2026, 1, 1),
        horizon_days=horizon_days,
        truth_fill_pct=truth_fill_pct,
        truth_is_overfull=truth_fill_pct is None,
        features=features,
    )


def make_features(**overrides) -> FeatureRow:
    defaults = dict(
        location_id="SYNTHETIC-f-x",
        material_type="brown",
        as_of_date=date(2026, 1, 1),
        month_of_as_of=1,
        n_readings=3,
        last_numeric_fill_pct=40,
        last_reading_is_overfull=False,
        days_since_last_reading=0,
        mean_numeric_fill_pct=40.0,
        max_numeric_fill_pct=40,
        overfull_share=0.0,
        fill_at_emptying_rate_pct_per_day=0.5,
        median_interval_days=28.0,
    )
    defaults.update(overrides)
    material: MaterialType = defaults["material_type"]
    return FeatureRow(**{**defaults, "material_type": material})


class TestPersistence:
    def test_persists_last_numeric_fill_and_overfull_state(self, forecast_dataset) -> None:
        cases = {
            (c.location_id, c.target_date): c for c in build_evaluation_cases(forecast_dataset)
        }
        record = forecast_persistence(cases[("SYNTHETIC-f-a", date(2026, 3, 1))])
        assert record is not None
        assert record.predicted_fill_pct == 40.0
        assert record.predicted_state == "overfull"  # last record is the token
        assert record.method == "persistence"
        assert record.horizon_days == 24

    def test_overfull_state_with_numeric_fallback(self) -> None:
        features = make_features(last_reading_is_overfull=True)
        record = forecast_persistence(make_case(features))
        assert record is not None
        assert record.predicted_state == "overfull"
        assert record.predicted_fill_pct == 40.0  # last numeric, token not coerced

    def test_numeric_100_is_full_state(self) -> None:
        features = make_features(last_numeric_fill_pct=100, max_numeric_fill_pct=100)
        record = forecast_persistence(make_case(features))
        assert record is not None
        assert record.predicted_state == "full"
        assert record.predicted_fill_pct == 100.0

    def test_no_numeric_history_returns_none(self) -> None:
        features = make_features(last_numeric_fill_pct=None, mean_numeric_fill_pct=None)
        assert forecast_persistence(make_case(features)) is None


class TestRate:
    def test_expected_fill_is_rate_times_median_interval(self) -> None:
        # 0.5 pp/day x 28 d median interval = 14.0 (independent of horizon_days).
        features = make_features(fill_at_emptying_rate_pct_per_day=0.5, median_interval_days=28.0)
        record = forecast_rate(make_case(features, horizon_days=30))
        assert record is not None
        assert record.predicted_fill_pct == 14.0
        assert record.predicted_state == "normal"
        assert record.method == "rate"
        assert record.horizon_days == 30  # echoed, not part of the v4 formula

    def test_clipped_to_observed_range(self) -> None:
        # 5.0 pp/day x 28 d = 140 → clipped to 100.
        features = make_features(fill_at_emptying_rate_pct_per_day=5.0)
        record = forecast_rate(make_case(features, horizon_days=30))
        assert record is not None
        assert record.predicted_fill_pct == 100.0
        assert record.predicted_state == "full"

    def test_zero_rate_is_a_valid_zero_prediction(self) -> None:
        features = make_features(fill_at_emptying_rate_pct_per_day=0.0)
        record = forecast_rate(make_case(features, horizon_days=30))
        assert record is not None
        assert record.predicted_fill_pct == 0.0
        assert record.predicted_state == "normal"

    def test_no_usable_rate_returns_none_no_fallback(self) -> None:
        # §2.3 v4: no usable rate ⇒ no numeric prediction — never persistence.
        features = make_features(fill_at_emptying_rate_pct_per_day=None)
        assert forecast_rate(make_case(features)) is None

    def test_no_median_interval_returns_none(self) -> None:
        features = make_features(median_interval_days=None)
        assert forecast_rate(make_case(features)) is None

    def test_no_numeric_history_returns_none(self) -> None:
        features = make_features(
            last_numeric_fill_pct=None,
            mean_numeric_fill_pct=None,
            fill_at_emptying_rate_pct_per_day=None,
        )
        assert forecast_rate(make_case(features)) is None

    def test_synthetic_overfull_only_series_unforecastable(self, forecast_dataset) -> None:
        cases = build_evaluation_cases(forecast_dataset)
        c_case = next(c for c in cases if c.location_id == "SYNTHETIC-f-c")
        assert forecast_persistence(c_case) is None
        assert forecast_rate(c_case) is None  # no numeric candidate in history


class TestDispatch:
    def test_forecast_dispatches_by_method(self) -> None:
        features = make_features()
        case = make_case(features, horizon_days=30)
        persistence = forecast(case, "persistence")
        rate = forecast(case, "rate")
        assert persistence is not None and rate is not None
        assert persistence.predicted_fill_pct == 40.0
        assert rate.predicted_fill_pct == 14.0

    def test_record_fields_match_contract_2_2(self) -> None:
        record = forecast_rate(make_case(make_features(), horizon_days=30))
        assert record is not None
        assert record.as_of_date == date(2026, 1, 1)
        assert record.target_date == date(2026, 1, 1)
        assert 0.0 <= record.predicted_fill_pct <= 100.0
        assert record.predicted_state in ("normal", "full", "overfull")
        assert record.material_type == "brown"
