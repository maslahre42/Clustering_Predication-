"""Per-bin profiles and descriptive K-Means groups; sparse bins remain visible."""
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from .data_loader import KEY, get_latest_readings, historical_prefix, planning_day


def extract_container_profiles(df, material_filter=None, *, as_of=None, inclusive=True):
    sub = historical_prefix(df, as_of, inclusive=inclusive)
    if material_filter is not None:
        sub = sub.loc[sub['material_type'].eq(material_filter)].copy()
    sub['_completed_censored'] = sub['cycle_is_censored'] & sub['cycle_rate_pct_per_day'].notna()
    profiles = sub.groupby(KEY, sort=True).agg(
        readings_count=('date', 'size'), numeric_readings=('fill_num', 'count'),
        avg_fill_perc=('fill_num', 'mean'), std_fill_perc=('fill_num', 'std'),
        max_fill_perc=('fill_num', 'max'), overfull_rate=('is_overfull', 'mean'),
        median_interval_days=('days_diff', 'median'),
        observed_cycle_rate=('cycle_rate_pct_per_day', 'median'),
        completed_cycles=('cycle_rate_pct_per_day', 'count'),
        censored_cycles=('_completed_censored', 'sum'),
    ).reset_index()
    profiles['std_fill_perc'] = profiles['std_fill_perc'].fillna(0)
    profiles['overfull_rate'] *= 100
    material_rates = sub.groupby('material_type')['cycle_rate_pct_per_day'].median()
    profiles['daily_fill_velocity'] = profiles['observed_cycle_rate'].fillna(profiles['material_type'].map(material_rates))
    profiles['rate_source'] = np.where(profiles['observed_cycle_rate'].notna(), 'bin_cycles',
        np.where(profiles['daily_fill_velocity'].notna(), 'material_cycles', 'unavailable'))
    latest = get_latest_readings(sub)[[*KEY, 'date', 'fill_num', 'is_overfull']].rename(columns={
        'date': 'last_reading_date', 'fill_num': 'last_pre_emptying_fill_perc', 'is_overfull': 'last_was_overfull'})
    profiles = profiles.merge(latest, on=KEY, validate='one_to_one')
    cutoff = planning_day(as_of) if as_of is not None else (sub['date'].max() if len(sub) else pd.NaT)
    profiles['profile_as_of'] = cutoff
    profiles['cutoff_inclusive'] = inclusive
    return profiles


def cluster_containers(profiles_df, n_clusters=4, random_state=42):
    if isinstance(n_clusters, bool) or not isinstance(n_clusters, int) or not 1 <= n_clusters <= 4:
        raise ValueError('n_clusters must be an integer from 1 to 4.')
    result = profiles_df.copy()
    features = ['avg_fill_perc', 'std_fill_perc', 'overfull_rate', 'daily_fill_velocity']
    eligible = result['readings_count'].ge(3) & np.isfinite(result[features]).all(axis=1)
    result['cluster'] = pd.Series(pd.NA, index=result.index, dtype='Int64')
    result['tier'] = 'Insufficient numeric history'
    if not eligible.any():
        return result, None
    values = result.loc[eligible, features].copy()
    values['daily_fill_velocity'] = np.log1p(values['daily_fill_velocity'])
    scaled = StandardScaler().fit_transform(values)
    k = min(n_clusters, len(values), len(np.unique(scaled, axis=0)))
    model = KMeans(n_clusters=k, random_state=random_state, n_init=10)
    labels = model.fit_predict(scaled)
    result.loc[eligible, 'cluster'] = labels
    ranked = result.loc[eligible].groupby('cluster')[['avg_fill_perc', 'overfull_rate']].mean().sum(axis=1).sort_values(ascending=False)
    names = {label: f'Group {rank + 1}: observed fill pressure' for rank, label in enumerate(ranked.index)}
    result.loc[eligible, 'tier'] = result.loc[eligible, 'cluster'].map(names)
    result.attrs['silhouette'] = (float(silhouette_score(scaled, labels, sample_size=min(len(values), 500), random_state=random_state)) if 1 < k < len(values) else None)
    result.attrs['cluster_sizes'] = {int(k): int(v) for k, v in result.loc[eligible, 'cluster'].value_counts().items()}
    result.attrs['grouping_note'] = 'Descriptive groups; no balanced-size or dispatch guarantee.'
    return result, model
