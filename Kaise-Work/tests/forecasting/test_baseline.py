"""Baseline tests — hand-computed persistence/rate behaviour (contract §2.3)."""

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
        median_rate_pct_per_day=0.5,
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
        assert record.predicted_state == "overfull"  # last reading is the token
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
    def test_projection_uses_median_rate_times_horizon(self) -> None:
        features = make_features(median_rate_pct_per_day=0.5)
        record = forecast_rate(make_case(features, horizon_days=30))
        assert record is not None
        assert record.predicted_fill_pct == 55.0  # 40 + 0.5 * 30
        assert record.predicted_state == "normal"
        assert record.method == "rate"

    def test_clipped_to_observed_range(self) -> None:
        features = make_features(last_numeric_fill_pct=90, median_rate_pct_per_day=0.5)
        record = forecast_rate(make_case(features, horizon_days=30))
        assert record is not None
        assert record.predicted_fill_pct == 100.0  # 90 + 15 clipped
        assert record.predicted_state == "full"

    def test_negative_projection_clipped_to_zero(self) -> None:
        features = make_features(last_numeric_fill_pct=10, median_rate_pct_per_day=-1.0)
        record = forecast_rate(make_case(features, horizon_days=30))
        assert record is not None
        assert record.predicted_fill_pct == 0.0

    def test_no_numeric_pair_falls_back_to_persistence(self) -> None:
        features = make_features(median_rate_pct_per_day=None)
        record = forecast_rate(make_case(features, horizon_days=30))
        assert record is not None
        assert record.predicted_fill_pct == 40.0  # = persistence value
        assert record.predicted_state == "normal"
        assert record.method == "rate"

    def test_no_numeric_history_returns_none(self) -> None:
        features = make_features(last_numeric_fill_pct=None, median_rate_pct_per_day=None)
        assert forecast_rate(make_case(features)) is None

    def test_synthetic_overfull_only_series_unforecastable(self, forecast_dataset) -> None:
        cases = build_evaluation_cases(forecast_dataset)
        c_case = next(c for c in cases if c.location_id == "SYNTHETIC-f-c")
        assert forecast_persistence(c_case) is None
        assert forecast_rate(c_case) is None


class TestDispatch:
    def test_forecast_dispatches_by_method(self) -> None:
        features = make_features()
        case = make_case(features, horizon_days=30)
        persistence = forecast(case, "persistence")
        rate = forecast(case, "rate")
        assert persistence is not None and rate is not None
        assert persistence.predicted_fill_pct == 40.0
        assert rate.predicted_fill_pct == 55.0

    def test_record_fields_match_contract_2_2(self) -> None:
        record = forecast_rate(make_case(make_features(), horizon_days=30))
        assert record is not None
        assert record.as_of_date == date(2026, 1, 1)
        assert record.target_date == date(2026, 1, 1)
        assert 0.0 <= record.predicted_fill_pct <= 100.0
        assert record.predicted_state in ("normal", "full", "overfull")
        assert record.material_type == "brown"
