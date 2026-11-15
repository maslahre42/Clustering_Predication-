"""Days-to-full v2 tests — hand-computed contract §5.2.3 behaviour (§1.5).

All fixtures are synthetic (SYNTHETIC- ids) and constructed from
:class:`ReadingRecord` directly; the fixture summary is derived from the
readings so no counter is fabricated. v4 semantics: one row is one emptying
event; rate = median fill_at_emptying / interval_days (never Δfill/Δdays).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.analytics.spatial import require_real_ids
from src.data.loader import load_glass_fill_csv
from src.data.schema import Dataset, DatasetSummary, MaterialType, ReadingRecord
from src.forecasting.days_to_full import (
    DEFAULT_TARGET_PCT,
    DaysToFullResult,
    build_days_to_full,
)
from src.forecasting.features import (
    collect_fill_at_emptying_rates_pct_per_day,
    collect_rate_candidates,
)
from tests.helpers import require_real_csv_path

BASE_DATE = date(2026, 1, 1)


def make_reading(
    location_id: str,
    material_type: MaterialType,
    day_offset: int,
    fill_pct: int | None,
    *,
    overfull: bool = False,
) -> ReadingRecord:
    """One synthetic emptying record; ``fill_pct`` must be None exactly when overfull (I3)."""
    return ReadingRecord(
        location_id=location_id,
        material_type=material_type,
        date=BASE_DATE + timedelta(days=day_offset),
        fill_level_pct=None if overfull else fill_pct,
        is_overfull=overfull,
    )


def make_dataset(readings: list[ReadingRecord]) -> Dataset:
    """Dataset whose summary counters are derived from the readings themselves."""
    return Dataset(
        readings=readings,
        summary=DatasetSummary(
            n_rows=len(readings),
            n_locations=len({reading.location_id for reading in readings}),
            n_series=len({(r.location_id, r.material_type) for r in readings}),
            date_min=min((reading.date for reading in readings), default=None),
            date_max=max((reading.date for reading in readings), default=None),
            rows_per_material={
                material: sum(1 for reading in readings if reading.material_type == material)
                for material in ("brown", "green", "white")
            },
        ),
    )


def happy_path_readings(location_id: str = "SYNTHETIC-df-a") -> list[ReadingRecord]:
    """40 @d0, 60 @d30 (rate 2.0/d), 90 @d60 (rate 3.0/d) — median rate 2.5."""
    return [
        make_reading(location_id, "brown", 0, 40),
        make_reading(location_id, "brown", 30, 60),
        make_reading(location_id, "brown", 60, 90),
    ]


class TestHappyPath:
    def test_hand_computed_estimate(self) -> None:
        result = build_days_to_full(make_dataset(happy_path_readings()))
        assert result.method == "fill_at_emptying_rate"
        assert result.target_pct == DEFAULT_TARGET_PCT == 90
        assert len(result.series) == 1
        row = result.series[0]
        # §1.5 rates: 60/30 = 2.0 and 90/30 = 3.0 pp/day → median 2.5
        assert row.rate_pct_per_day == pytest.approx(2.5)
        assert row.median_interval_days == 30.0
        # days_to_full = target_pct / rate = 90 / 2.5 = 36.0
        assert row.days_to_full == 36.0
        # predicted_full_date = last emptying (d60) + round(36.0) = d96; never clamped
        assert row.predicted_full_date == BASE_DATE + timedelta(days=96)
        assert row.is_lower_bound is False
        assert row.reason is None
        assert row.last_emptying_date == BASE_DATE + timedelta(days=60)
        assert row.last_fill_pct == 90
        assert row.last_is_overfull is False

    def test_two_records_hand_computed(self) -> None:
        # 40 @d0, 80 @d40: single rate 80/40 = 2.0 → days = 90/2.0 = 45.0
        readings = [
            make_reading("SYNTHETIC-df-a2", "green", 0, 40),
            make_reading("SYNTHETIC-df-a2", "green", 40, 80),
        ]
        row = build_days_to_full(make_dataset(readings)).series[0]
        assert row.rate_pct_per_day == pytest.approx(2.0)
        assert row.median_interval_days == 40.0
        assert row.days_to_full == 45.0
        assert row.predicted_full_date == BASE_DATE + timedelta(days=85)

    def test_stats_single_series(self) -> None:
        stats = build_days_to_full(make_dataset(happy_path_readings())).stats
        assert stats.series_total == 1
        assert stats.series_with_estimate == 1
        assert stats.median_days == 36.0
        assert stats.mean_days == 36.0
        assert stats.min_days == 36.0
        assert stats.max_days == 36.0
        assert stats.lower_bound_share_pct == 0.0


class TestReasons:
    def test_single_record_is_not_enough_records(self) -> None:
        readings = [make_reading("SYNTHETIC-df-e", "brown", 0, 60)]
        row = build_days_to_full(make_dataset(readings)).series[0]
        assert row.reason == "not_enough_records"
        assert row.days_to_full is None
        assert row.predicted_full_date is None
        assert row.rate_pct_per_day is None
        assert row.median_interval_days is None
        assert row.last_emptying_date == BASE_DATE
        assert row.last_fill_pct == 60
        assert row.is_lower_bound is False

    def test_same_day_records_are_zero_interval_only(self) -> None:
        # Two records, both on d0: the only interval is 0 days (§5.2.3 excludes it).
        readings = [
            make_reading("SYNTHETIC-df-f", "brown", 0, 20),
            make_reading("SYNTHETIC-df-f", "brown", 0, 25),
        ]
        row = build_days_to_full(make_dataset(readings)).series[0]
        assert row.reason == "zero_interval_only"
        assert row.days_to_full is None
        assert row.rate_pct_per_day is None
        assert row.median_interval_days is None

    def test_positive_interval_beside_zero_interval_is_usable(self) -> None:
        # d0 (40), d0 (41), d20 (53): the 0-day pair is skipped, 53/20 is the rate.
        readings = [
            make_reading("SYNTHETIC-df-i", "green", 0, 40),
            make_reading("SYNTHETIC-df-i", "green", 0, 41),
            make_reading("SYNTHETIC-df-i", "green", 20, 53),
        ]
        row = build_days_to_full(make_dataset(readings)).series[0]
        assert row.reason is None
        assert row.rate_pct_per_day == pytest.approx(53 / 20)
        assert row.median_interval_days == 20.0
        assert row.days_to_full == round(90 / (53 / 20), 1)

    def test_overfull_candidates_only_is_no_numeric_fill(self) -> None:
        # Numeric record first, then two overfull records: candidates exist but
        # none has a numeric fill — the median is never fabricated.
        readings = [
            make_reading("SYNTHETIC-df-g", "brown", 0, 40),
            make_reading("SYNTHETIC-df-g", "brown", 30, None, overfull=True),
            make_reading("SYNTHETIC-df-g", "brown", 60, None, overfull=True),
        ]
        row = build_days_to_full(make_dataset(readings)).series[0]
        assert row.reason == "no_numeric_fill"
        assert row.days_to_full is None
        assert row.predicted_full_date is None
        assert row.rate_pct_per_day is None
        assert row.median_interval_days == 30.0  # intervals are date-based
        assert row.is_lower_bound is True  # overfull candidates flag censored evidence
        assert row.last_fill_pct is None
        assert row.last_is_overfull is True

    def test_zero_rate_candidates_is_zero_rate_not_fabricated(self) -> None:
        # Both contributing fills are 0 → median rate 0 → target/0 undefined.
        readings = [
            make_reading("SYNTHETIC-df-j", "white", 0, 0),
            make_reading("SYNTHETIC-df-j", "white", 30, 0),
        ]
        row = build_days_to_full(make_dataset(readings)).series[0]
        assert row.reason == "zero_rate"
        assert row.days_to_full is None
        assert row.predicted_full_date is None
        assert row.rate_pct_per_day == 0.0


class TestLowerBound:
    def test_capped_100_candidate_sets_lower_bound(self) -> None:
        # Contributing fill 100 is a censored lower bound (§1.5): never coerced.
        readings = [
            make_reading("SYNTHETIC-df-b", "green", 0, 40),
            make_reading("SYNTHETIC-df-b", "green", 30, 100),
        ]
        row = build_days_to_full(make_dataset(readings)).series[0]
        assert row.is_lower_bound is True
        assert row.rate_pct_per_day == pytest.approx(100 / 30)  # 100 stays numeric
        assert row.days_to_full == round(90 / (100 / 30), 1)
        assert row.reason is None

    def test_overfull_candidate_sets_lower_bound_without_entering_median(self) -> None:
        # Candidates: overfull @d30 (no numeric value) and 60/30 = 2.0 @d60.
        readings = [
            make_reading("SYNTHETIC-df-c", "brown", 0, 40),
            make_reading("SYNTHETIC-df-c", "brown", 30, None, overfull=True),
            make_reading("SYNTHETIC-df-c", "brown", 60, 60),
        ]
        row = build_days_to_full(make_dataset(readings)).series[0]
        assert row.is_lower_bound is True
        assert row.rate_pct_per_day == pytest.approx(2.0)  # overfull never in median
        assert row.days_to_full == 45.0

    def test_censored_first_record_does_not_flag(self) -> None:
        # The numeric-100 record is d0 (not a candidate: i >= 2 required).
        readings = [
            make_reading("SYNTHETIC-df-d", "brown", 0, 100),
            make_reading("SYNTHETIC-df-d", "brown", 30, 60),
        ]
        row = build_days_to_full(make_dataset(readings)).series[0]
        assert row.is_lower_bound is False
        assert row.rate_pct_per_day == pytest.approx(2.0)

    def test_stats_lower_bound_share(self) -> None:
        readings = [
            make_reading("SYNTHETIC-df-k", "brown", 0, 40),
            make_reading("SYNTHETIC-df-k", "brown", 30, 100),  # estimate, lower bound
            make_reading("SYNTHETIC-df-l", "green", 0, 40),
            make_reading("SYNTHETIC-df-l", "green", 30, 80),  # estimate, not lower bound
            make_reading("SYNTHETIC-df-m", "white", 0, 40),  # no estimate (1 record)
        ]
        stats = build_days_to_full(make_dataset(readings)).stats
        assert stats.series_with_estimate == 2
        assert stats.lower_bound_share_pct == 50.0  # 1 of 2 estimates flagged

    def test_lower_bound_share_none_without_estimates(self) -> None:
        readings = [
            make_reading("SYNTHETIC-df-n", "brown", 0, 40),
            make_reading("SYNTHETIC-df-n", "brown", 30, None, overfull=True),
        ]
        stats = build_days_to_full(make_dataset(readings)).stats
        assert stats.series_with_estimate == 0
        assert stats.lower_bound_share_pct is None


class TestTargetPct:
    def test_target_pct_50_halves_days_to_full(self) -> None:
        result = build_days_to_full(make_dataset(happy_path_readings()), target_pct=50)
        assert result.target_pct == 50
        assert result.series[0].days_to_full == 20.0  # 50 / 2.5

    def test_target_pct_bounds_validated(self) -> None:
        dataset = make_dataset(happy_path_readings())
        for bad in (0, -1, 101):
            with pytest.raises(ValueError, match="target_pct"):
                build_days_to_full(dataset, target_pct=bad)
        assert build_days_to_full(dataset, target_pct=1).series[0].days_to_full == 0.4
        assert build_days_to_full(dataset, target_pct=100).series[0].days_to_full == 40.0

    def test_target_pct_label_in_assumptions(self) -> None:
        result = build_days_to_full(make_dataset(happy_path_readings()), target_pct=75)
        assert "target fill 75% [demo assumption — slide mockup]" in result.assumptions


class TestAggregatesAndOrder:
    def test_stats_and_stats_by_material(self) -> None:
        # brown: 36.0 (estimate), green: no_numeric_fill, white: estimate at rate 100/14.
        readings = [
            *happy_path_readings("SYNTHETIC-df-p"),
            make_reading("SYNTHETIC-df-q", "green", 0, 40),
            make_reading("SYNTHETIC-df-q", "green", 30, None, overfull=True),
            make_reading("SYNTHETIC-df-r", "white", 0, 60),
            make_reading("SYNTHETIC-df-r", "white", 14, 100),  # rate 100/14, lower bound
        ]
        result = build_days_to_full(make_dataset(readings))
        stats = result.stats
        assert stats.series_total == 3
        assert stats.series_with_estimate == 2
        white_days = round(90 / (100 / 14), 1)
        assert stats.median_days == (36.0 + white_days) / 2
        assert stats.lower_bound_share_pct == 50.0

        brown = result.stats_by_material["brown"]
        assert brown.series_total == 1
        assert brown.series_with_estimate == 1
        assert brown.median_days == 36.0
        green = result.stats_by_material["green"]
        assert green.series_total == 1
        assert green.series_with_estimate == 0
        assert green.median_days is None
        assert green.lower_bound_share_pct is None
        white = result.stats_by_material["white"]
        assert white.series_with_estimate == 1
        assert white.lower_bound_share_pct == 100.0

    def test_stats_by_material_always_has_three_keys(self) -> None:
        result = build_days_to_full(make_dataset(happy_path_readings()))
        assert set(result.stats_by_material) == {"brown", "green", "white"}

    def test_no_estimates_all_stats_null(self) -> None:
        readings = [
            make_reading("SYNTHETIC-df-s", "brown", 0, 60),
            make_reading("SYNTHETIC-df-s", "brown", 0, 70),
        ]
        stats = build_days_to_full(make_dataset(readings)).stats
        assert stats.series_total == 1
        assert stats.series_with_estimate == 0
        assert stats.median_days is None
        assert stats.mean_days is None
        assert stats.min_days is None
        assert stats.max_days is None
        assert stats.lower_bound_share_pct is None

    def test_empty_dataset(self) -> None:
        result = build_days_to_full(Dataset.empty())
        assert result.method == "fill_at_emptying_rate"
        assert result.series == []
        assert result.stats.series_total == 0
        assert result.stats.series_with_estimate == 0
        assert result.stats.median_days is None
        assert result.stats.lower_bound_share_pct is None
        assert all(
            stats.series_total == 0 and stats.median_days is None
            for stats in result.stats_by_material.values()
        )

    def test_series_sorted_by_location_then_material(self) -> None:
        readings = [
            make_reading("SYNTHETIC-df-z", "brown", 0, 50),
            make_reading("SYNTHETIC-df-a", "green", 0, 50),
        ]
        keys = [
            (row.location_id, row.material_type)
            for row in build_days_to_full(make_dataset(readings)).series
        ]
        assert keys == [("SYNTHETIC-df-a", "green"), ("SYNTHETIC-df-z", "brown")]


class TestDeterminism:
    def test_same_input_same_output(self) -> None:
        shuffled = list(reversed(happy_path_readings()))  # unsorted input rows
        first: DaysToFullResult = build_days_to_full(make_dataset(happy_path_readings()))
        second: DaysToFullResult = build_days_to_full(make_dataset(shuffled))
        assert first == second  # includes series order, stats and assumptions

    def test_unsorted_input_same_per_series_values(self) -> None:
        shuffled = [
            make_reading("SYNTHETIC-df-o", "brown", 60, 90),
            make_reading("SYNTHETIC-df-o", "brown", 0, 40),
            make_reading("SYNTHETIC-df-o", "brown", 30, 60),
        ]
        row = build_days_to_full(make_dataset(shuffled)).series[0]
        assert row.days_to_full == 36.0
        assert row.last_emptying_date == BASE_DATE + timedelta(days=60)


class TestAssumptions:
    def test_mandatory_section_1_5_caveat_present(self) -> None:
        result = build_days_to_full(make_dataset(happy_path_readings()))
        assert any(
            "fill at emptying shows how full the container was when the schedule "
            "reached it — not how fast it would have filled" in label
            for label in result.assumptions
        )
        assert any(
            "no unobserved emptying between records" in label for label in result.assumptions
        )
        assert any("refills from 0 after each emptying" in label for label in result.assumptions)
        assert any("target fill 90%" in label for label in result.assumptions)


class TestRateHelperReuse:
    def test_candidates_and_rates_come_from_features_helpers(self) -> None:
        # §5.2.3 candidates: records i >= 2 with interval > 0; overfull records
        # are candidates without a numeric value. Reuse, not duplication.
        readings = [
            make_reading("SYNTHETIC-df-t", "brown", 0, 40),
            make_reading("SYNTHETIC-df-t", "brown", 30, None, overfull=True),
            make_reading("SYNTHETIC-df-t", "brown", 60, 60),
        ]
        candidates = collect_rate_candidates(readings)
        assert [record.is_overfull for record, _days in candidates] == [True, False]
        assert [days for _record, days in candidates] == [30, 30]
        assert collect_fill_at_emptying_rates_pct_per_day(readings) == pytest.approx([2.0])


class TestRealCsvPins:
    """Guarded regression pins (aggregate counts only, no raw rows).

    Produced 2026-11-14 by ``build_days_to_full`` on the real challenge CSV
    via the canonical loader; numbers also recorded in docs/model_card.md.
    """

    def test_v2_aggregates_match_model_card(self) -> None:
        result = load_glass_fill_csv(require_real_csv_path())
        assert not result.errors, f"real CSV must load cleanly: {result.errors[:3]}"
        require_real_ids(result.dataset.readings)
        result_dtf = build_days_to_full(result.dataset)
        assert (result_dtf.method, result_dtf.target_pct) == ("fill_at_emptying_rate", 90)
        stats = result_dtf.stats
        assert (stats.series_total, stats.series_with_estimate) == (1338, 1303)
        assert (stats.median_days, stats.mean_days) == (59.3, pytest.approx(101.7006, abs=0.001))
        assert (stats.min_days, stats.max_days) == (6.6, 2313.0)
        assert stats.lower_bound_share_pct == 66.5
        by_material = result_dtf.stats_by_material
        assert (by_material["brown"].series_with_estimate, by_material["brown"].median_days) == (
            422,
            pytest.approx(121.95, abs=0.001),
        )
        assert (by_material["green"].series_with_estimate, by_material["green"].median_days) == (
            439,
            52.0,
        )
        assert (by_material["white"].series_with_estimate, by_material["white"].median_days) == (
            442,
            pytest.approx(38.05, abs=0.001),
        )
        reasons = [row.reason for row in result_dtf.series]
        assert reasons.count("not_enough_records") == 34
        assert reasons.count("no_numeric_fill") == 1
        assert reasons.count("zero_interval_only") == 0
        assert reasons.count("zero_rate") == 0
        assert sum(1 for row in result_dtf.series if row.is_lower_bound) == 868
