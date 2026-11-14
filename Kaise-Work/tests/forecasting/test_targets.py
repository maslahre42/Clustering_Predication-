"""Targets tests — hand-computed cases on the synthetic fixture (contract §2.1).

Fixture (tests/fixtures/synthetic_forecast.csv), per-series readings:
- SYNTHETIC-f-a/brown: 01-10:40, 02-05:overfull, 03-01:60, 04-20:80
- SYNTHETIC-f-b/green: 01-15:30, 03-15:90
- SYNTHETIC-f-c/white: 02-01:overfull, 03-01:overfull
- SYNTHETIC-f-d/brown: 05-02:50 (single reading -> no cases)
"""

from __future__ import annotations

from datetime import date

from src.data.schema import Dataset
from src.forecasting.targets import EvaluationCase, build_evaluation_cases


def _by_key(cases: list[EvaluationCase]) -> dict[tuple[str, date], EvaluationCase]:
    return {(c.location_id, c.target_date): c for c in cases}


class TestBuildEvaluationCases:
    def test_expected_cases_deterministically_ordered(self, forecast_dataset) -> None:
        cases = build_evaluation_cases(forecast_dataset)
        keys = [(c.location_id, c.material_type, c.target_date) for c in cases]
        assert len(cases) == 5  # (4-1) + (2-1) + (2-1) + (1-1)
        assert keys == sorted(keys)  # location_id, material, target_date
        assert keys == [
            ("SYNTHETIC-f-a", "brown", date(2026, 2, 5)),
            ("SYNTHETIC-f-a", "brown", date(2026, 3, 1)),
            ("SYNTHETIC-f-a", "brown", date(2026, 4, 20)),
            ("SYNTHETIC-f-b", "green", date(2026, 3, 15)),
            ("SYNTHETIC-f-c", "white", date(2026, 3, 1)),
        ]

    def test_first_readings_excluded_and_horizons(self, forecast_dataset) -> None:
        cases = build_evaluation_cases(forecast_dataset)
        by_key = _by_key(cases)
        assert date(2026, 1, 10) not in {c.target_date for c in cases}
        assert date(2026, 1, 15) not in {c.target_date for c in cases}
        assert by_key[("SYNTHETIC-f-a", date(2026, 2, 5))].as_of_date == date(2026, 1, 10)
        assert by_key[("SYNTHETIC-f-a", date(2026, 2, 5))].horizon_days == 26
        assert by_key[("SYNTHETIC-f-a", date(2026, 3, 1))].horizon_days == 24
        assert by_key[("SYNTHETIC-f-a", date(2026, 4, 20))].horizon_days == 50
        assert by_key[("SYNTHETIC-f-b", date(2026, 3, 15))].horizon_days == 59

    def test_truth_preserves_overfull_token(self, forecast_dataset) -> None:
        by_key = _by_key(build_evaluation_cases(forecast_dataset))
        overfull_case = by_key[("SYNTHETIC-f-a", date(2026, 2, 5))]
        assert overfull_case.truth_is_overfull is True
        assert overfull_case.truth_fill_pct is None  # never coerced (§2.4)
        numeric_case = by_key[("SYNTHETIC-f-a", date(2026, 3, 1))]
        assert numeric_case.truth_fill_pct == 60
        assert numeric_case.truth_is_overfull is False

    def test_invariant_truth_none_iff_overfull_and_horizon_positive(self, forecast_dataset) -> None:
        for case in build_evaluation_cases(forecast_dataset):
            assert (case.truth_fill_pct is None) == case.truth_is_overfull
            assert case.horizon_days >= 1

    def test_deterministic_across_calls(self, forecast_dataset) -> None:
        assert build_evaluation_cases(forecast_dataset) == build_evaluation_cases(forecast_dataset)

    def test_empty_dataset_yields_no_cases(self) -> None:
        assert build_evaluation_cases(Dataset.empty()) == []
