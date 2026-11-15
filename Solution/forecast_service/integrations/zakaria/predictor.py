"""Transparent reset-aware cycle-median baseline; not a calibrated risk model."""
import numpy as np
import pandas as pd
from .data_loader import KEY, planning_day


def predict_container_demands(profiles_df, days_ahead=2, holiday_multiplier=1.0,
                              container_volume_m3=3.0, glass_density_kg_m3=350.0,
                              *, planning_date=None):
    if planning_date is None:
        raise ValueError('Supply one explicit planning_date for all bins.')
    day = planning_day(planning_date)
    if isinstance(days_ahead, bool) or not isinstance(days_ahead, int) or days_ahead < 0:
        raise ValueError('days_ahead must be a nonnegative integer.')
    for name, value in [('holiday_multiplier', holiday_multiplier), ('container_volume_m3', container_volume_m3), ('glass_density_kg_m3', glass_density_kg_m3)]:
        if isinstance(value, bool) or not np.isfinite(value) or value <= 0:
            raise ValueError(f'{name} must be positive and finite.')
    df = profiles_df.copy()
    last = pd.to_datetime(df['last_reading_date'])
    cutoff = pd.to_datetime(df['profile_as_of'])
    if (last >= day).any() or (cutoff > day).any() or ((cutoff == day) & df['cutoff_inclusive'].eq(True)).any():
        raise ValueError('Morning forecasts require profiles built strictly before planning_date.')
    rate = pd.to_numeric(df['daily_fill_velocity'], errors='coerce')
    if (rate.dropna() < 0).any() or np.isinf(rate).any():
        raise ValueError('Cycle rates must be nonnegative, finite or unavailable.')
    target = day + pd.Timedelta(days=days_ahead)
    elapsed = (target - last).dt.days
    df['planning_date'] = day
    df['target_date'] = target
    df['days_since_emptying_at_target'] = elapsed
    df['predicted_fill_perc'] = (rate * elapsed * holiday_multiplier).clip(0, 100)
    df['forecast_available'] = rate.notna()
    df['forecast_method'] = 'cycle_median_lower_bound'
    df['holiday_multiplier'] = holiday_multiplier
    df['container_volume_m3'] = container_volume_m3
    df['glass_density_kg_m3'] = glass_density_kg_m3
    df['demand_volume_m3'] = df['predicted_fill_perc'] / 100 * container_volume_m3
    df['demand_weight_kg'] = df['demand_volume_m3'] * glass_density_kg_m3
    df['urgency_status'] = np.select(
        [rate.isna(), df['predicted_fill_perc'].ge(80), df['predicted_fill_perc'].ge(60)],
        ['Unknown: no completed cycles', 'Urgent (>=80%)', 'Opportunistic (60-79%)'], default='Safe (<60%)')
    return df


def select_collection_sites(demands, threshold=80.0, opportunistic_threshold=60.0):
    if not 0 <= opportunistic_threshold <= threshold <= 100:
        raise ValueError('Require 0 <= opportunistic_threshold <= threshold <= 100.')
    if demands.duplicated(KEY).any():
        raise ValueError('Duplicate bin identities.')
    decisions = demands.copy()
    due = decisions['predicted_fill_perc'].ge(threshold)
    site_due = due.groupby(decisions['Location_id']).transform('any')
    extra = site_due & decisions['predicted_fill_perc'].ge(opportunistic_threshold)
    decisions['selected'] = due | extra
    decisions['selection_reason'] = np.select([~decisions['forecast_available'], due, extra],
        ['no_forecast', 'at_or_above_threshold', 'same_site_opportunistic'], default='below_threshold')
    selected = decisions.loc[decisions['selected']]
    sites = selected.groupby('Location_id', sort=True).agg(
        predicted_fill_perc=('predicted_fill_perc', 'max'), demand_volume_m3=('demand_volume_m3', 'sum'),
        demand_weight_kg=('demand_weight_kg', 'sum'), n_bins=('material_type', 'size'),
        materials=('material_type', lambda s: ','.join(sorted(s))),
    ).reset_index()
    sites = sites.sort_values(['predicted_fill_perc', 'Location_id'], ascending=[False, True]).reset_index(drop=True)
    return sites, decisions
