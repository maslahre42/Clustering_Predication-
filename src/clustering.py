import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from typing import Tuple

def extract_container_profiles(df: pd.DataFrame, material_filter: str = None) -> pd.DataFrame:
    """
    Computes behavioral profiles per container or location, separating emptying drops from true accumulation.
    """
    sub = df.copy()
    if material_filter:
        sub = sub[sub['material_type'] == material_filter].copy()

    # Calculate true positive daily accumulation velocity
    pos = sub[(sub['fill_diff'] >= 0) & (sub['days_diff'] > 0)].copy()
    pos['daily_vel'] = pos['fill_diff'] / pos['days_diff']
    vel_by_loc = pos.groupby('Location_id')['daily_vel'].median()

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
    profiles['daily_fill_velocity'] = profiles['Location_id'].map(vel_by_loc).fillna(0.65)
    profiles = profiles.merge(latest, on='Location_id', how='left')

    return profiles

def cluster_containers(profiles_df: pd.DataFrame, n_clusters: int = 4, random_state: int = 42) -> Tuple[pd.DataFrame, KMeans]:
    """
    Clusters containers into behavioral operational tiers based on fill level, overfull propensity, and fill speed.
    """
    df_clust = profiles_df.copy()
    features = ['avg_fill_perc', 'std_fill_perc', 'overfull_rate', 'daily_fill_velocity']
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df_clust[features])
    
    kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    df_clust['cluster'] = kmeans.fit_predict(X_scaled)
    
    # Sort cluster IDs by urgency (descending by avg_fill_perc + overfull_rate)
    urgency_score = df_clust.groupby('cluster').apply(
        lambda g: g['avg_fill_perc'].mean() + g['overfull_rate'].mean()
    ).sort_values(ascending=False)
    
    tier_names = [
        'Tier 1: Critical / Chronic High-Volume',
        'Tier 2: Steady High-Demand',
        'Tier 3: Moderate Regular',
        'Tier 4: Low-Demand / Sporadic'
    ]
    
    cluster_to_tier = {cid: tier_names[i % len(tier_names)] for i, cid in enumerate(urgency_score.index)}
    df_clust['tier'] = df_clust['cluster'].map(cluster_to_tier)
    
    return df_clust, kmeans
