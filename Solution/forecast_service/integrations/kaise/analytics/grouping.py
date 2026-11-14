"""Container grouping by behaviour (M3) — k-means only if interpretable.

Groups glass-fill series by behavioural features (src.analytics.series_features).
Two paths, decided by data — never by preference:

1. **k-means** (scikit-learn, seeded ``random_state=42``) on standardised
   features, applied only when an explicit *interpretability gate* passes:
   - silhouette >= ``MIN_SILHOUETTE`` for the best k in 2..4;
   - every cluster has at least ``MIN_CLUSTER_SIZE`` series;
   - every cluster pair differs (IQRs do not overlap) on at least
     ``MIN_SEPARATING_FEATURES`` of the raw features.
2. **rule-based pressure tiers** (always available fallback): descriptive
   cut-offs on observed fill pressure ``share_at_100 + overfull_share``.
   Cut-off defaults are analyst-chosen descriptive labels for THIS dataset,
   NOT business thresholds (business thresholds are M7 territory, contract §3).

Series with too little history (``n_readings < 3``) or without computable
features (e.g. all readings overfull) are excluded from clustering and labelled
``insufficient_history``; they are never silently dropped.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from itertools import combinations

from sklearn.cluster import KMeans  # type: ignore[import-untyped]  # no py.typed marker
from sklearn.metrics import (  # type: ignore[import-untyped]
    silhouette_score,
)

from integrations.kaise.analytics.series_features import SeriesFeatures

GROUPING_FEATURES: tuple[str, ...] = (
    "n_readings",
    "median_gap_days",
    "mean_fill_pct",
    "overfull_share",
    "share_at_100",
    "median_rate_pct_per_day",
)
RANDOM_STATE = 42  # seeded k-means: results reproducible run-to-run
KMEANS_N_INIT = 10
K_CANDIDATES: tuple[int, ...] = (2, 3, 4)
MIN_READINGS = 3  # need >= 3 readings for cadence + numeric pairs
MIN_SILHOUETTE = 0.35  # below this, clusters are not well separated
MIN_CLUSTER_SIZE = 5  # smaller clusters are not operationally interpretable
MIN_SEPARATING_FEATURES = 2  # cluster pairs must differ clearly on >= 2 features

TIER_INSUFFICIENT = "insufficient_history"
TIER_HIGH = "high_pressure"
TIER_MEDIUM = "medium_pressure"
TIER_LOW = "low_pressure"
# Descriptive cut-offs on fill pressure = share_at_100 + overfull_share:
# chosen from this dataset's observed distribution, documented in
# docs/eda_report.md; NOT business thresholds.
HIGH_PRESSURE_MIN = 0.30
MEDIUM_PRESSURE_MIN = 0.10


@dataclass(frozen=True)
class ClusterProfile:
    """Median behavioural profile of one cluster/tier."""

    label: str
    n_series: int
    feature_medians: dict[str, float]


@dataclass(frozen=True)
class GroupingResult:
    """Outcome of grouping: chosen method, gate evidence, labels for ALL series."""

    method: str  # "kmeans" (gate passed) | "rule_tiers" (gate failed/skipped)
    chosen_k: int | None
    silhouette_by_k: dict[int, float]
    gate: dict[str, bool]  # keys: silhouette, min_cluster_size, separability
    profiles: tuple[ClusterProfile, ...]
    labels: dict[tuple[str, str], str]  # (location_id, material_type) -> label
    n_eligible: int
    n_excluded_insufficient: int


def fill_pressure(feature: SeriesFeatures) -> float:
    """share_at_100 + overfull_share — share of readings at/over full (fraction)."""
    return feature.share_at_100 + feature.overfull_share


def tier_labels(
    features: list[SeriesFeatures],
    min_readings: int = MIN_READINGS,
    high_pressure_min: float = HIGH_PRESSURE_MIN,
    medium_pressure_min: float = MEDIUM_PRESSURE_MIN,
) -> dict[tuple[str, str], str]:
    """Rule-based descriptive tier per series (all series labelled)."""
    labels: dict[tuple[str, str], str] = {}
    for f in features:
        key = (f.location_id, f.material_type)
        if f.n_readings < min_readings or f.mean_fill_pct is None:
            labels[key] = TIER_INSUFFICIENT
            continue
        pressure = fill_pressure(f)
        if pressure >= high_pressure_min:
            labels[key] = TIER_HIGH
        elif pressure >= medium_pressure_min:
            labels[key] = TIER_MEDIUM
        else:
            labels[key] = TIER_LOW
    return labels


def eligible_for_clustering(features: list[SeriesFeatures]) -> list[SeriesFeatures]:
    """Series with enough history AND all clustering features computable."""
    eligible: list[SeriesFeatures] = []
    for f in features:
        if f.n_readings < MIN_READINGS or f.n_numeric < 2:
            continue
        if all(getattr(f, name) is not None for name in GROUPING_FEATURES):
            eligible.append(f)
    return eligible


def _feature_values(feature: SeriesFeatures) -> list[float]:
    return [float(getattr(feature, name)) for name in GROUPING_FEATURES]


def _standardize(matrix: list[list[float]]) -> list[list[float]]:
    """Column-wise z-scores; columns with zero spread become all-zero."""
    n_cols = len(GROUPING_FEATURES)
    means = [statistics.mean(col) for col in zip(*matrix, strict=True)]
    stds = [statistics.pstdev(col) for col in zip(*matrix, strict=True)]
    standardized: list[list[float]] = []
    for row in matrix:
        standardized.append(
            [(row[c] - means[c]) / stds[c] if stds[c] > 0 else 0.0 for c in range(n_cols)]
        )
    return standardized


def _quantiles(values: list[float]) -> tuple[float, float]:
    """(p25, p75) with linear interpolation; well-defined for >= 2 values."""
    q1, _, q3 = statistics.quantiles(values, n=4, method="inclusive")
    return q1, q3


def _iqr_nonoverlap_count(rows_a: list[list[float]], rows_b: list[list[float]]) -> int:
    """Number of features whose cluster IQRs do not overlap (raw units)."""
    separating = 0
    for c in range(len(GROUPING_FEATURES)):
        col_a = [row[c] for row in rows_a]
        col_b = [row[c] for row in rows_b]
        q1a, q3a = _quantiles(col_a)
        q1b, q3b = _quantiles(col_b)
        if q3a < q1b or q3b < q1a:
            separating += 1
    return separating


def _cluster_medians(rows: list[list[float]]) -> dict[str, float]:
    return {
        name: float(statistics.median([row[c] for row in rows]))
        for c, name in enumerate(GROUPING_FEATURES)
    }


def cluster_or_tier(features: list[SeriesFeatures]) -> GroupingResult:
    """Group series by k-means if the interpretability gate passes, else tiers."""
    tiers = tier_labels(features)
    eligible = eligible_for_clustering(features)
    n_excluded = len(features) - len(eligible)
    tiers_only = GroupingResult(
        method="rule_tiers",
        chosen_k=None,
        silhouette_by_k={},
        gate={},
        profiles=_profiles_by_label(features, tiers),
        labels=tiers,
        n_eligible=len(eligible),
        n_excluded_insufficient=n_excluded,
    )
    if len(eligible) < 2 * MIN_CLUSTER_SIZE:
        return tiers_only

    matrix = [_feature_values(f) for f in eligible]
    standardized = _standardize(matrix)
    silhouette_by_k: dict[int, float] = {}
    for k in K_CANDIDATES:
        if k >= len(eligible):
            continue
        model = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=KMEANS_N_INIT)
        cluster_ids = [int(x) for x in model.fit_predict(standardized)]
        if len(set(cluster_ids)) < 2:
            continue
        silhouette_by_k[k] = float(silhouette_score(standardized, cluster_ids))
    if not silhouette_by_k:
        return tiers_only

    # Best silhouette; ties broken toward the smaller k (simpler solution).
    best_k = max(silhouette_by_k, key=lambda k: (silhouette_by_k[k], -k))
    model = KMeans(n_clusters=best_k, random_state=RANDOM_STATE, n_init=KMEANS_N_INIT)
    cluster_ids = [int(x) for x in model.fit_predict(standardized)]

    members: dict[int, list[int]] = {}
    for idx, cluster in enumerate(cluster_ids):
        members.setdefault(cluster, []).append(idx)
    size_ok = min(len(v) for v in members.values()) >= MIN_CLUSTER_SIZE
    silhouette_ok = silhouette_by_k[best_k] >= MIN_SILHOUETTE
    separability_ok = all(
        _iqr_nonoverlap_count([matrix[i] for i in members[a]], [matrix[i] for i in members[b]])
        >= MIN_SEPARATING_FEATURES
        for a, b in combinations(members, 2)
    )
    gate = {
        "silhouette": silhouette_ok,
        "min_cluster_size": size_ok,
        "separability": separability_ok,
    }
    if not all(gate.values()):
        from dataclasses import replace
        return replace(tiers_only, gate=gate, silhouette_by_k=silhouette_by_k)

    # Deterministic cluster naming: order by median mean_fill_pct ascending.
    order = sorted(
        members,
        key=lambda c: (statistics.median([matrix[i][2] for i in members[c]]), c),
    )
    rename = {cluster: f"cluster-{rank + 1}" for rank, cluster in enumerate(order)}
    labels = dict(tiers)
    for idx, cluster in enumerate(cluster_ids):
        key = (eligible[idx].location_id, eligible[idx].material_type)
        labels[key] = rename[cluster]
    profiles = tuple(
        ClusterProfile(
            label=rename[cluster],
            n_series=len(members[cluster]),
            feature_medians=_cluster_medians([matrix[i] for i in members[cluster]]),
        )
        for cluster in order
    )
    return GroupingResult(
        method="kmeans",
        chosen_k=best_k,
        silhouette_by_k=silhouette_by_k,
        gate=gate,
        profiles=profiles,
        labels=labels,
        n_eligible=len(eligible),
        n_excluded_insufficient=n_excluded,
    )


def _profiles_by_label(
    features: list[SeriesFeatures], labels: dict[tuple[str, str], str]
) -> tuple[ClusterProfile, ...]:
    """Median feature profile per tier (rule path; None-safe medians)."""
    by_label: dict[str, list[SeriesFeatures]] = {}
    for f in features:
        label = labels[(f.location_id, f.material_type)]
        by_label.setdefault(label, []).append(f)
    profiles: list[ClusterProfile] = []
    for label in sorted(by_label):
        members = by_label[label]
        medians: dict[str, float] = {}
        for name in GROUPING_FEATURES:
            values = [float(getattr(f, name)) for f in members if getattr(f, name) is not None]
            medians[name] = float(statistics.median(values)) if values else None
        profiles.append(ClusterProfile(label=label, n_series=len(members), feature_medians=medians))
    return tuple(profiles)
