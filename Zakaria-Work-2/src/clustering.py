import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    silhouette_score,
    davies_bouldin_score,
    calinski_harabasz_score,
    adjusted_rand_score
)
from typing import Tuple, Sequence, Optional, Dict, Any


def audit_collection_reset_evidence(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Audits empirical evidence in the dataset regarding whether observations represent
    collection visits (which reset fill levels) vs. passive continuous sensor logs.
    """
    sub = df.copy()
    if 'days_diff' not in sub.columns or 'prev_fill' not in sub.columns or 'fill_diff' not in sub.columns:
        if 'fill_num' not in sub.columns:
            sub['fill_num'] = sub['fill_level_perc'].apply(
                lambda x: 110.0 if str(x).strip().lower() == 'overfull' else float(x)
            )
        sub['date'] = pd.to_datetime(sub['date'])
        grp_cols = ['Location_id', 'material_type'] if 'material_type' in sub.columns else ['Location_id']
        sub = sub.sort_values(grp_cols + ['date']).reset_index(drop=True)
        sub['prev_date'] = sub.groupby(grp_cols)['date'].shift(1)
        sub['prev_fill'] = sub.groupby(grp_cols)['fill_num'].shift(1)
        sub['days_diff'] = (sub['date'] - sub['prev_date']).dt.days
        sub['fill_diff'] = sub['fill_num'] - sub['prev_fill']

    valid = sub[sub['days_diff'].notna() & (sub['days_diff'] > 0)].copy()
    high_to_high = ((valid['prev_fill'] >= 80.0) & (valid['fill_num'] >= 80.0)).mean() * 100.0
    neg_drops = (valid['fill_diff'] < 0).mean() * 100.0
    zero_diffs_at_100 = ((valid['prev_fill'] >= 100.0) & (valid['fill_num'] >= 100.0)).mean() * 100.0

    return {
        "total_intervals": int(len(valid)),
        "median_interval_days": float(valid['days_diff'].median()) if len(valid) > 0 else 0.0,
        "mean_interval_days": round(float(valid['days_diff'].mean()), 1) if len(valid) > 0 else 0.0,
        "consecutive_high_to_high_pct": round(float(high_to_high), 1) if len(valid) > 0 else 0.0,
        "consecutive_100_to_100_pct": round(float(zero_diffs_at_100), 1) if len(valid) > 0 else 0.0,
        "apparent_negative_fill_diff_pct": round(float(neg_drops), 1) if len(valid) > 0 else 0.0,
    }


def extract_container_profiles(
    df: pd.DataFrame,
    material_filter: Optional[str] = None,
    residual_fill_perc: float = 0.0,
    data_semantics: str = "collection_visit_reset"
) -> pd.DataFrame:
    """
    Computes behavioral profiles per container.
    Supports two explicit data semantics modes:
      - 'collection_visit_reset': Each reading is a pre-emptying record at a truck visit;
        velocity = (fill_num - residual_fill_perc) / days_diff.
      - 'continuous_sensor': Readings are passive sensor logs; velocity is estimated from
        positive non-emptying increments (fill_diff > 0) / days_diff.
    """
    sub = df.copy()
    if 'fill_num' not in sub.columns:
        sub['fill_num'] = sub['fill_level_perc'].apply(
            lambda x: 110.0 if str(x).strip().lower() == 'overfull' else float(x)
        )
    if 'is_overfull' not in sub.columns:
        sub['is_overfull'] = (
            sub['fill_level_perc'].astype(str).str.strip().str.lower() == 'overfull'
        ) | (sub['fill_num'] > 100.0)

    if material_filter:
        sub = sub[sub['material_type'] == material_filter].copy()
        group_cols = ['Location_id']
    else:
        group_cols = (
            ['Location_id', 'material_type']
            if 'material_type' in sub.columns and sub['material_type'].nunique() > 1
            else ['Location_id']
        )

    if 'days_diff' not in sub.columns:
        sub['date'] = pd.to_datetime(sub['date'])
        sub = sub.sort_values(group_cols + ['date']).reset_index(drop=True)
        sub['prev_date'] = sub.groupby(group_cols)['date'].shift(1)
        sub['prev_fill'] = sub.groupby(group_cols)['fill_num'].shift(1)
        sub['days_diff'] = (sub['date'] - sub['prev_date']).dt.days
        sub['fill_diff'] = sub['fill_num'] - sub['prev_fill']

    valid_intervals = sub[(sub['days_diff'] > 0) & (sub['days_diff'] <= 180)].copy()

    if data_semantics == "continuous_sensor":
        pos_intervals = valid_intervals[valid_intervals['fill_diff'] > 0].copy()
        pos_intervals['daily_vel'] = pos_intervals['fill_diff'] / pos_intervals['days_diff']
    else:
        valid_intervals['daily_vel'] = (valid_intervals['fill_num'] - residual_fill_perc) / valid_intervals['days_diff']
        pos_intervals = valid_intervals[valid_intervals['daily_vel'] > 0].copy()

    vel_by_key = pos_intervals.groupby(group_cols)['daily_vel'].median()
    global_median_vel = float(pos_intervals['daily_vel'].median()) if len(pos_intervals) > 0 else 2.5

    latest = (
        sub.sort_values('date')
        .groupby(group_cols)
        .last()
        .reset_index()[group_cols + ['date', 'fill_num', 'is_overfull']]
    )
    latest = latest.rename(columns={'date': 'last_reading_date', 'fill_num': 'current_fill_perc'})

    profiles = sub.groupby(group_cols).agg(
        readings_count=('fill_num', 'count'),
        avg_fill_perc=('fill_num', 'mean'),
        std_fill_perc=('fill_num', 'std'),
        max_fill_perc=('fill_num', 'max'),
        overfull_rate=('is_overfull', lambda x: (x.sum() / len(x)) * 100.0)
    ).reset_index()

    profiles['std_fill_perc'] = profiles['std_fill_perc'].fillna(0.0)
    vel_df = vel_by_key.reset_index().rename(columns={'daily_vel': 'daily_fill_velocity'})
    profiles = profiles.merge(vel_df, on=group_cols, how='left')
    profiles['daily_fill_velocity'] = profiles['daily_fill_velocity'].fillna(global_median_vel)
    profiles = profiles.merge(latest, on=group_cols, how='left')
    profiles['data_semantics'] = data_semantics

    return profiles


def evaluate_clustering_metrics(
    profiles_df: pd.DataFrame,
    k_range: Sequence[int] = (3, 4, 5),
    random_state: int = 42
) -> pd.DataFrame:
    """
    Evaluates K-Means geometric clustering quality across k_range.
    """
    features = ['avg_fill_perc', 'std_fill_perc', 'overfull_rate', 'daily_fill_velocity']
    X_scaled = StandardScaler().fit_transform(profiles_df[features])

    results = []
    for k in k_range:
        kmeans = KMeans(n_clusters=k, random_state=random_state, n_init=10)
        labels = kmeans.fit_predict(X_scaled)
        results.append({
            'k': k,
            'Silhouette Score': round(float(silhouette_score(X_scaled, labels)), 4),
            'Davies-Bouldin Index': round(float(davies_bouldin_score(X_scaled, labels)), 4),
            'Calinski-Harabasz Index': round(float(calinski_harabasz_score(X_scaled, labels)), 2),
            'Inertia': round(float(kmeans.inertia_), 2)
        })
    return pd.DataFrame(results)


def evaluate_cluster_stability(
    profiles_df: pd.DataFrame,
    n_clusters: int = 4,
    seeds: Sequence[int] = (42, 7, 123, 999, 2026)
) -> Dict[str, float]:
    """
    Tests K-Means cluster stability across multiple random initialization seeds
    using pairwise Adjusted Rand Index (ARI, where 1.0 = identical partitions).
    """
    features = ['avg_fill_perc', 'std_fill_perc', 'overfull_rate', 'daily_fill_velocity']
    X_scaled = StandardScaler().fit_transform(profiles_df[features])

    label_sets = []
    for s in seeds:
        km = KMeans(n_clusters=n_clusters, random_state=s, n_init=10)
        label_sets.append(km.fit_predict(X_scaled))

    aris = []
    for i in range(len(seeds)):
        for j in range(i + 1, len(seeds)):
            aris.append(float(adjusted_rand_score(label_sets[i], label_sets[j])))

    return {
        "n_clusters": n_clusters,
        "num_seeds_tested": len(seeds),
        "mean_pairwise_ari": round(float(np.mean(aris)), 4),
        "min_pairwise_ari": round(float(np.min(aris)), 4),
        "max_pairwise_ari": round(float(np.max(aris)), 4)
    }


def cluster_containers(
    profiles_df: pd.DataFrame,
    n_clusters: int = 4,
    random_state: int = 42
) -> Tuple[pd.DataFrame, KMeans]:
    """
    Clusters containers into behavioral operational tiers sorted by a composite
    operational severity index (standardized avg_fill_perc + overfull_rate + daily_fill_velocity).
    Supports any k >= 2 without modulo label collisions.
    """
    df_clust = profiles_df.copy()
    features = ['avg_fill_perc', 'std_fill_perc', 'overfull_rate', 'daily_fill_velocity']

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df_clust[features])

    kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    df_clust['cluster'] = kmeans.fit_predict(X_scaled)

    # Rank clusters by composite operational severity (mean fill + overfull rate + velocity)
    cluster_means = df_clust.groupby('cluster')[features].mean()
    severity_score = (
        cluster_means['avg_fill_perc'] / 100.0 +
        cluster_means['overfull_rate'] / 100.0 +
        cluster_means['daily_fill_velocity'] / 5.0
    )
    sorted_clusters = severity_score.sort_values(ascending=False).index.tolist()

    default_four_names = [
        'Tier 1: Critical High-Volume / Chronic Overfillers',
        'Tier 2: Steady High-Demand',
        'Tier 3: Moderate Regular',
        'Tier 4: Low-Demand / Sporadic'
    ]

    cluster_to_tier = {}
    for rank_idx, cid in enumerate(sorted_clusters):
        if n_clusters == 4 and rank_idx < len(default_four_names):
            cluster_to_tier[cid] = default_four_names[rank_idx]
        else:
            m_fill = cluster_means.loc[cid, 'avg_fill_perc']
            m_ovf = cluster_means.loc[cid, 'overfull_rate']
            cluster_to_tier[cid] = f"Tier {rank_idx + 1} (Mean Fill {m_fill:.0f}%, Overfull {m_ovf:.0f}%)"

    df_clust['tier'] = df_clust['cluster'].map(cluster_to_tier)
    return df_clust, kmeans
