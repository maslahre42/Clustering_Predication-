import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score, davies_bouldin_score, calinski_harabasz_score
from typing import Tuple, Sequence, Dict

def extract_container_profiles(
    df: pd.DataFrame,
    material_filter: str = None,
    residual_fill_perc: float = 0.0
) -> pd.DataFrame:
    """
    Computes behavioral profiles per container or location.
    
    Operational Reality:
    Every historical record in the PreZero dataset represents a collection visit that emptied
    the container down to residual_fill_perc (default 0.0%). Therefore, the true waste accumulation
    between consecutive visits is (fill_num - residual_fill_perc) over days_diff days.
    True daily accumulation velocity is computed as (fill_num - residual_fill_perc) / days_diff.
    """
    sub = df.copy()
    if material_filter:
        sub = sub[sub['material_type'] == material_filter].copy()

    # Calculate true operational daily accumulation velocity
    # Each record represents accumulation from residual_fill_perc to fill_num over days_diff days
    valid_intervals = sub[(sub['days_diff'] > 0) & (sub['days_diff'] <= 180)].copy()
    valid_intervals['daily_vel'] = (valid_intervals['fill_num'] - residual_fill_perc) / valid_intervals['days_diff']
    # Filter out anomalous zero or negative velocities if any
    pos_intervals = valid_intervals[valid_intervals['daily_vel'] > 0]
    vel_by_loc = pos_intervals.groupby('Location_id')['daily_vel'].median()
    global_median_vel = pos_intervals['daily_vel'].median() if len(pos_intervals) > 0 else 2.5

    # Latest reading per container
    latest = sub.sort_values('date').groupby('Location_id').last().reset_index()[['Location_id', 'date', 'fill_num', 'is_overfull']]
    latest = latest.rename(columns={'date': 'last_reading_date', 'fill_num': 'current_fill_perc'})

    # Aggregate historical metrics
    profiles = sub.groupby('Location_id').agg(
        readings_count=('fill_num', 'count'),
        avg_fill_perc=('fill_num', 'mean'),
        std_fill_perc=('fill_num', 'std'),
        max_fill_perc=('fill_num', 'max'),
        overfull_rate=('is_overfull', lambda x: (x.sum() / len(x)) * 100)
    ).reset_index()

    profiles['std_fill_perc'] = profiles['std_fill_perc'].fillna(0.0)
    profiles['daily_fill_velocity'] = profiles['Location_id'].map(vel_by_loc).fillna(global_median_vel)
    profiles = profiles.merge(latest, on='Location_id', how='left')

    return profiles

def evaluate_clustering_metrics(
    profiles_df: pd.DataFrame,
    k_range: Sequence[int] = (3, 4, 5),
    random_state: int = 42
) -> pd.DataFrame:
    """
    Evaluates K-Means clustering quality across different cluster numbers (k) using standard
    mathematical validation metrics:
      - Silhouette Score (higher is better, range [-1, 1]): measures cohesion within clusters and separation from neighbors.
      - Davies-Bouldin Index (lower is better, range [0, inf)): ratio of within-cluster distance to between-cluster separation.
      - Calinski-Harabasz Index (higher is better): ratio of between-cluster dispersion to within-cluster dispersion (Variance Ratio).
      - Inertia (Sum of squared distances to centroids).
    """
    features = ['avg_fill_perc', 'std_fill_perc', 'overfull_rate', 'daily_fill_velocity']
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(profiles_df[features])

    results = []
    for k in k_range:
        kmeans = KMeans(n_clusters=k, random_state=random_state, n_init=10)
        labels = kmeans.fit_predict(X_scaled)
        
        sil = silhouette_score(X_scaled, labels)
        db = davies_bouldin_score(X_scaled, labels)
        ch = calinski_harabasz_score(X_scaled, labels)
        
        results.append({
            'k': k,
            'Silhouette Score': round(sil, 4),
            'Davies-Bouldin Index': round(db, 4),
            'Calinski-Harabasz Index': round(ch, 2),
            'Inertia': round(kmeans.inertia_, 2)
        })

    eval_df = pd.DataFrame(results)
    return eval_df

def cluster_containers(
    profiles_df: pd.DataFrame,
    n_clusters: int = 4,
    random_state: int = 42
) -> Tuple[pd.DataFrame, KMeans]:
    """
    Clusters containers into behavioral operational tiers based on fill level, overfull propensity,
    volatility, and fill speed.
    
    Cleanly maps clusters to the 4 standard operational tiers:
      - Tier 1: Critical High-Volume / Chronic Overfillers (Urgent high-frequency dispatch)
      - Tier 2: Steady High-Demand (Predictable high fill, consistent cycles)
      - Tier 3: Moderate Regular (Standard municipal collection schedule)
      - Tier 4: Low-Demand / Sporadic (Slow accumulation, on-demand/sweep)
    """
    df_clust = profiles_df.copy()
    features = ['avg_fill_perc', 'std_fill_perc', 'overfull_rate', 'daily_fill_velocity']
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df_clust[features])
    
    kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    df_clust['cluster'] = kmeans.fit_predict(X_scaled)
    
    # Sort cluster IDs by urgency (descending by avg_fill_perc to map to operational priority)
    cluster_means = df_clust.groupby('cluster')[features].mean()
    sorted_clusters = cluster_means.sort_values(by='avg_fill_perc', ascending=False).index.tolist()
    
    tier_names = [
        'Tier 1: Critical High-Volume / Chronic Overfillers',
        'Tier 2: Steady High-Demand',
        'Tier 3: Moderate Regular',
        'Tier 4: Low-Demand / Sporadic'
    ]
    
    cluster_to_tier = {cid: tier_names[i % len(tier_names)] for i, cid in enumerate(sorted_clusters)}
    df_clust['tier'] = df_clust['cluster'].map(cluster_to_tier)
    
    return df_clust, kmeans
