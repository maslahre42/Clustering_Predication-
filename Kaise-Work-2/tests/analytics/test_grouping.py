"""Tests for src.analytics.grouping — tiered/k-means grouping with gate.

Fixture: tests/fixtures/synthetic_grouping.csv (SYNTHETIC): 6 high-pressure
series (fills 90/100/overfull/100, 7-day gaps), 6 low-pressure series (fills
10..20, 30-day gaps), 2 insufficient-history series. The gate decision
(k-means only if interpretable) is exercised on both fixture data and
hand-built SeriesFeatures.
"""

from datetime import date
from pathlib import Path

from src.analytics.grouping import (
    MIN_CLUSTER_SIZE,
    MIN_SEPARATING_FEATURES,
    MIN_SILHOUETTE,
    TIER_HIGH,
    TIER_INSUFFICIENT,
    TIER_LOW,
    _iqr_nonoverlap_count,
    cluster_or_tier,
    eligible_for_clustering,
    fill_pressure,
    tier_labels,
)
from src.analytics.series_features import SeriesFeatures
from src.data.loader import load_glass_fill_csv
from src.data.schema import Dataset

FIXTURES = Path("tests/fixtures")


def _load(name: str) -> Dataset:
    result = load_glass_fill_csv(FIXTURES / name)
    assert not result.errors, f"fixture {name} must load cleanly: {result.errors}"
    return result.dataset


def _features(name: str) -> list[SeriesFeatures]:
    from src.analytics.series_features import compute_series_features

    return compute_series_features(_load(name).readings)


def _feature(
    location_id: str,
    mean_fill_pct: float,
    share_at_100: float,
    overfull_share: float,
    median_gap_days: float = 10.0,
    median_rate_pct_per_day: float = 0.5,
    n_readings: int = 4,
) -> SeriesFeatures:
    """Hand-built SeriesFeatures for gate/fallback tests (descriptive values)."""
    return SeriesFeatures(
        location_id=location_id,
        material_type="brown",
        n_readings=n_readings,
        n_numeric=n_readings,
        n_overfull=round(overfull_share * n_readings),
        first_date=date(2026, 1, 1),
        last_date=date(2026, 3, 1),
        span_days=59,
        median_gap_days=median_gap_days,
        mean_gap_days=median_gap_days,
        mean_fill_pct=mean_fill_pct,
        overfull_share=overfull_share,
        share_at_100=share_at_100,
        mean_delta_pct=median_rate_pct_per_day * median_gap_days,
        median_rate_pct_per_day=median_rate_pct_per_day,
        mean_positive_rate_pct_per_day=(
            median_rate_pct_per_day if median_rate_pct_per_day > 0 else None
        ),
        mean_negative_rate_pct_per_day=(
            median_rate_pct_per_day if median_rate_pct_per_day < 0 else None
        ),
        n_increase_pairs=1,
        n_decrease_events=0,
    )


class TestFillPressure:
    def test_pressure_sums_shares(self) -> None:
        f = _feature("x", mean_fill_pct=95, share_at_100=0.5, overfull_share=0.25)
        assert fill_pressure(f) == 0.75


class TestTierLabels:
    def test_fixture_tiers(self) -> None:
        labels = tier_labels(_features("synthetic_grouping.csv"))
        highs = [v for k, v in labels.items() if "-h" in k[0]]
        lows = [v for k, v in labels.items() if "-l" in k[0]]
        singles = {k: v for k, v in labels.items() if "-s" in k[0]}
        assert set(highs) == {TIER_HIGH}  # pressure 0.5 + 0.25 = 0.75 >= 0.30
        assert set(lows) == {TIER_LOW}  # pressure 0.0 < 0.10
        assert set(singles.values()) == {TIER_INSUFFICIENT}

    def test_medium_band(self) -> None:
        f = _feature("m", mean_fill_pct=60, share_at_100=0.0, overfull_share=0.2)
        labels = tier_labels([f])
        assert labels[("m", "brown")] == "medium_pressure"  # 0.10 <= 0.20 < 0.30


class TestEligibility:
    def test_fixture_eligibility(self) -> None:
        features = _features("synthetic_grouping.csv")
        eligible_keys = {
            (f.location_id, f.material_type) for f in eligible_for_clustering(features)
        }
        assert len(eligible_keys) == 12
        assert all("-s" not in key[0] for key in eligible_keys)

    def test_overfull_only_series_excluded(self) -> None:
        f = _feature("all-overfull", mean_fill_pct=100, share_at_100=0.0, overfull_share=1.0)
        f = SeriesFeatures(
            **{
                **f.__dict__,
                "mean_fill_pct": None,
                "median_rate_pct_per_day": None,
                "mean_positive_rate_pct_per_day": None,
            }
        )
        assert eligible_for_clustering([f]) == []


class TestClusteringOnFixture:
    def test_gate_passes_and_clusters_separate_groups(self) -> None:
        result = cluster_or_tier(_features("synthetic_grouping.csv"))
        assert result.method == "kmeans"
        assert result.chosen_k == 2
        assert result.gate == {
            "silhouette": True,
            "min_cluster_size": True,
            "separability": True,
        }
        assert result.silhouette_by_k[result.chosen_k] >= MIN_SILHOUETTE
        assert result.n_eligible == 12
        assert result.n_excluded_insufficient == 2

        labels = result.labels
        high_label = labels[("SYNTHETIC-grp-h1", "brown")]
        low_label = labels[("SYNTHETIC-grp-l1", "brown")]
        assert low_label != high_label
        # Same behavioural group -> same cluster (h4/l4 are the brown members).
        assert labels[("SYNTHETIC-grp-h4", "brown")] == high_label
        assert labels[("SYNTHETIC-grp-l4", "brown")] == low_label
        assert labels[("SYNTHETIC-grp-s1", "white")] == TIER_INSUFFICIENT
        assert labels[("SYNTHETIC-grp-s2", "brown")] == TIER_INSUFFICIENT

        sizes = sorted(p.n_series for p in result.profiles)
        assert sizes == [6, 6]
        assert all(p.n_series >= MIN_CLUSTER_SIZE for p in result.profiles)
        medians = {p.label: p.feature_medians["mean_fill_pct"] for p in result.profiles}
        low_profile = next(p for p in result.profiles if p.label == low_label)
        high_profile = next(p for p in result.profiles if p.label == high_label)
        assert (
            low_profile.feature_medians["mean_fill_pct"]
            < high_profile.feature_medians["mean_fill_pct"]
        )
        assert set(medians) == {low_label, high_label}

    def test_deterministic_across_runs(self) -> None:
        features = _features("synthetic_grouping.csv")
        assert cluster_or_tier(features) == cluster_or_tier(features)


class TestFallbackToTiers:
    def test_too_few_eligible_series_uses_tiers(self) -> None:
        features = [
            _feature("a", 95, 0.5, 0.25),
            _feature("b", 96, 0.5, 0.25),
            _feature("c", 15, 0.0, 0.0, median_gap_days=30, median_rate_pct_per_day=0.3),
            _feature("d", 16, 0.0, 0.0, median_gap_days=30, median_rate_pct_per_day=0.3),
        ]
        result = cluster_or_tier(features)
        assert result.method == "rule_tiers"
        assert result.chosen_k is None
        assert result.gate == {}
        assert result.silhouette_by_k == {}
        assert result.n_eligible == 4
        labels = result.labels
        assert labels[("a", "brown")] == TIER_HIGH
        assert labels[("c", "brown")] == TIER_LOW

    def test_gate_failure_uses_tiers(self) -> None:
        # 10+ eligible series drawn from one homogeneous population: k-means fits,
        # but clusters are NOT separable (IQRs overlap on every feature).
        import random

        rng = random.Random(7)
        features = [
            _feature(
                f"g{i}",
                mean_fill_pct=50 + rng.uniform(-5, 5),
                share_at_100=0.2 + rng.uniform(-0.02, 0.02),
                overfull_share=0.1,
                median_gap_days=20 + rng.uniform(-2, 2),
                median_rate_pct_per_day=0.5 + rng.uniform(-0.05, 0.05),
                n_readings=8,
            )
            for i in range(12)
        ]
        result = cluster_or_tier(features)
        assert result.method == "rule_tiers"
        assert result.gate == {} or not all(result.gate.values())


class TestIqrSeparabilityHelper:
    def test_separated_clusters_count_features(self) -> None:
        a = [[90, 7, 95, 0.25, 0.5, 1.4], [95, 7, 96, 0.25, 0.5, 1.4]]
        b = [[10, 30, 15, 0.0, 0.0, 0.3], [20, 30, 16, 0.0, 0.0, 0.3]]
        assert _iqr_nonoverlap_count(a, b) >= MIN_SEPARATING_FEATURES

    def test_overlapping_clusters_count_zero(self) -> None:
        a = [[50, 20, 60, 0.1, 0.2, 0.5], [55, 20, 62, 0.1, 0.2, 0.5]]
        b = [[52, 20, 61, 0.1, 0.2, 0.5], [57, 20, 63, 0.1, 0.2, 0.5]]
        assert _iqr_nonoverlap_count(a, b) == 0
