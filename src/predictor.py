import pandas as pd
import numpy as np
import holidays
from sklearn.metrics import mean_absolute_error, mean_squared_error
from typing import Optional, Union, Dict, Tuple, Any


def _count_bw_holiday_days_between(start_dt: pd.Timestamp, end_dt: pd.Timestamp) -> int:
    """Counts Baden-Württemberg holiday/festive days inside (start_dt, end_dt]."""
    if pd.isna(start_dt) or pd.isna(end_dt) or end_dt <= start_dt:
        return 0
    years = list(range(start_dt.year, end_dt.year + 1))
    try:
        de_bw = holidays.Germany(subdiv='BW', years=years)
    except Exception:
        de_bw = holidays.Germany(prov='BW', years=years)
    cur = start_dt.date() + pd.Timedelta(days=1)
    end_d = end_dt.date()
    h_days = 0
    while cur <= end_d:
        if cur in de_bw or (cur.month == 12 and cur.day >= 20) or (cur.month == 1 and cur.day <= 6):
            h_days += 1
        cur += pd.Timedelta(days=1)
    return h_days


def predict_container_demands(
    profiles_df: pd.DataFrame,
    days_ahead: int = 2,
    reference_date: Optional[Union[str, pd.Timestamp]] = None,
    days_since_last_collection: Optional[Union[int, float, pd.Series]] = None,
    residual_fill_perc: float = 0.0,
    holiday_multiplier: float = 1.0,
    container_volume_m3: float = 2.5,
    glass_density_kg_m3: float = 380.0,
    data_semantics: str = "collection_visit_reset"
) -> pd.DataFrame:
    """
    Velocity-based physical demand estimation model.
    Supports both:
      - 'collection_visit_reset': Fill_pred = min(110%, residual_fill_perc + v_i * delta_t * S_eff)
      - 'continuous_sensor': Fill_pred = min(110%, current_fill_perc + v_i * days_ahead * S_eff)
    """
    df_pred = profiles_df.copy()

    if data_semantics == "continuous_sensor":
        delta_t = float(max(days_ahead, 0))
        base_fill = df_pred['current_fill_perc'].astype(float)
    else:
        base_fill = float(residual_fill_perc)
        if days_since_last_collection is not None:
            delta_t = days_since_last_collection + float(days_ahead)
        elif 'last_reading_date' in df_pred.columns:
            last_dates = pd.to_datetime(df_pred['last_reading_date'])
            ref_dt = pd.to_datetime(reference_date) if reference_date is not None else last_dates.max()
            elapsed_days = (ref_dt - last_dates).dt.days
            delta_t = (elapsed_days + days_ahead).clip(lower=0)
        else:
            delta_t = float(max(days_ahead, 0))

    df_pred['days_since_last_collection'] = delta_t

    # Interval-based holiday multiplier if dates are available and holiday_multiplier != 1.0
    if 'last_reading_date' in df_pred.columns and holiday_multiplier != 1.0:
        last_dates = pd.to_datetime(df_pred['last_reading_date'])
        ref_dt = pd.to_datetime(reference_date) if reference_date is not None else last_dates.max()
        target_dt = ref_dt + pd.Timedelta(days=days_ahead)
        h_days_series = [
            _count_bw_holiday_days_between(t_last, target_dt) if pd.notna(t_last) else 0
            for t_last in last_dates
        ]
        df_pred['holiday_days_in_interval'] = h_days_series
        dt_denom = delta_t.clip(lower=1) if isinstance(delta_t, pd.Series) else max(float(delta_t), 1.0)
        eff_mult = 1.0 + (holiday_multiplier - 1.0) * (np.array(h_days_series) / dt_denom)
        target_is_holiday = _count_bw_holiday_days_between(target_dt - pd.Timedelta(days=1), target_dt) > 0
        if target_is_holiday:
            eff_mult = np.maximum(eff_mult, holiday_multiplier)
    else:
        eff_mult = holiday_multiplier

    projected_growth = df_pred['daily_fill_velocity'] * delta_t * eff_mult
    df_pred['uncapped_fill_perc'] = (base_fill + projected_growth).round(2)
    df_pred['predicted_fill_perc'] = (base_fill + projected_growth).clip(upper=110.0).round(1)

    fill_ratio = df_pred['predicted_fill_perc'] / 100.0
    df_pred['demand_volume_m3'] = (fill_ratio * container_volume_m3).round(2)
    df_pred['demand_weight_kg'] = (df_pred['demand_volume_m3'] * glass_density_kg_m3).round(1)

    def categorize_urgency(val: float) -> str:
        if val >= 80.0:
            return 'Urgent (>=80%)'
        elif val >= 60.0:
            return 'Opportunistic (60-79%)'
        else:
            return 'Safe (<60%)'

    df_pred['urgency_status'] = df_pred['predicted_fill_perc'].apply(categorize_urgency)
    return df_pred


def validate_fill_predictor(
    df: pd.DataFrame,
    material_filter: str = 'white',
    train_ratio: float = 0.8,
    residual_fill_perc: float = 0.0,
    holiday_multiplier: float = 1.25
) -> Tuple[Dict[str, Any], pd.DataFrame]:
    """
    Validates velocity-based demand estimation on an 80/20 chronological split.
    1. Uses interval-based holiday exposure (proportion of holiday days within [prev_date, date]).
    2. Evaluates uncensored ordinary readings (0-100%) separately from right-censored
       'overfull' (>100%) observations.
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

    sub['date'] = pd.to_datetime(sub['date'])
    if 'prev_date' in sub.columns:
        sub['prev_date'] = pd.to_datetime(sub['prev_date'])
    else:
        grp = ['Location_id', 'material_type'] if 'material_type' in sub.columns else ['Location_id']
        sub = sub.sort_values(grp + ['date']).reset_index(drop=True)
        sub['prev_date'] = sub.groupby(grp)['date'].shift(1)
        sub['prev_fill'] = sub.groupby(grp)['fill_num'].shift(1)
        sub['days_diff'] = (sub['date'] - sub['prev_date']).dt.days
        sub['fill_diff'] = sub['fill_num'] - sub['prev_fill']

    if material_filter:
        sub = sub[sub['material_type'] == material_filter].copy()

    sub = sub.sort_values('date').reset_index(drop=True)
    valid = sub[(sub['days_diff'] > 0) & (sub['days_diff'] <= 180)].copy()

    split_idx = int(len(valid) * train_ratio)
    split_date = valid.iloc[split_idx]['date']

    train = valid[valid['date'] < split_date].copy()
    test = valid[valid['date'] >= split_date].copy()

    train['daily_vel'] = (train['fill_num'] - residual_fill_perc) / train['days_diff']
    train_pos = train[train['daily_vel'] > 0]
    vel_by_loc = train_pos.groupby('Location_id')['daily_vel'].median()
    global_median_vel = float(train_pos['daily_vel'].median()) if len(train_pos) > 0 else 2.5

    test['pred_vel'] = test['Location_id'].map(vel_by_loc).fillna(global_median_vel)

    # Interval-proportional holiday multiplier
    holiday_window_days = [
        _count_bw_holiday_days_between(r['prev_date'], r['date'])
        for _, r in test.iterrows()
    ]
    test['holiday_days_in_interval'] = holiday_window_days
    test['interval_holiday_factor'] = 1.0 + (holiday_multiplier - 1.0) * (
        test['holiday_days_in_interval'] / test['days_diff'].clip(lower=1)
    )
    # Also support endpoint holiday boost if collection falls directly on holiday window
    if 'is_holiday' in test.columns:
        endpoint_boost = test['is_holiday'].apply(lambda h: holiday_multiplier if h else 1.0)
    else:
        endpoint_boost = pd.Series(1.0, index=test.index)
    eff_mult = np.maximum(test['interval_holiday_factor'], endpoint_boost)

    test['pred_fill'] = (residual_fill_perc + test['pred_vel'] * test['days_diff'] * eff_mult).clip(upper=110.0)

    # Naive cumulative baseline
    train_old_pos = train[(train['fill_diff'] >= 0) & (train['days_diff'] > 0)]
    old_vel_by_loc = (train_old_pos['fill_diff'] / train_old_pos['days_diff']).groupby(train_old_pos['Location_id']).median()
    test['old_vel'] = test['Location_id'].map(old_vel_by_loc).fillna(0.65)
    test['old_pred_fill'] = (test['prev_fill'] + test['old_vel'] * test['days_diff']).clip(upper=110.0)

    # Overall metrics (including 110% proxy for overfull)
    mae_model = mean_absolute_error(test['fill_num'], test['pred_fill'])
    rmse_model = np.sqrt(mean_squared_error(test['fill_num'], test['pred_fill']))
    mae_baseline = mean_absolute_error(test['fill_num'], test['old_pred_fill'])
    rmse_baseline = np.sqrt(mean_squared_error(test['fill_num'], test['old_pred_fill']))

    # Uncensored metrics (ordinary readings <= 100% only, excluding right-censored 'overfull')
    uncensored = test[~test['is_overfull']].copy()
    mae_uncensored = mean_absolute_error(uncensored['fill_num'], uncensored['pred_fill'].clip(upper=100.0))
    rmse_uncensored = np.sqrt(mean_squared_error(uncensored['fill_num'], uncensored['pred_fill'].clip(upper=100.0)))

    # Urgent (>=80%) and Overfull (>=100% / is_overfull) detection accuracy
    actual_urgent = test['fill_num'] >= 80.0
    pred_urgent = test['pred_fill'] >= 80.0
    urgent_recall = (actual_urgent & pred_urgent).sum() / max(actual_urgent.sum(), 1) * 100.0
    urgent_precision = (actual_urgent & pred_urgent).sum() / max(pred_urgent.sum(), 1) * 100.0

    actual_overfull = test['is_overfull'] if 'is_overfull' in test.columns else (test['fill_num'] >= 105.0)
    pred_overfull = test['pred_fill'] >= 100.0
    overfull_recall = (actual_overfull & pred_overfull).sum() / max(actual_overfull.sum(), 1) * 100.0
    overfull_precision = (actual_overfull & pred_overfull).sum() / max(pred_overfull.sum(), 1) * 100.0

    metrics = {
        'train_samples': int(len(train)),
        'test_samples': int(len(test)),
        'uncensored_test_samples': int(len(uncensored)),
        'censored_overfull_test_samples': int(test['is_overfull'].sum()),
        'train_date_range': f"{train['date'].min().strftime('%Y-%m-%d')} to {train['date'].max().strftime('%Y-%m-%d')}",
        'test_date_range': f"{test['date'].min().strftime('%Y-%m-%d')} to {test['date'].max().strftime('%Y-%m-%d')}",
        'mae': round(float(mae_model), 2),
        'rmse': round(float(rmse_model), 2),
        'uncensored_mae': round(float(mae_uncensored), 2),
        'uncensored_rmse': round(float(rmse_uncensored), 2),
        'urgent_recall_pct': round(float(urgent_recall), 1),
        'urgent_precision_pct': round(float(urgent_precision), 1),
        'overfull_recall_pct': round(float(overfull_recall), 1),
        'overfull_precision_pct': round(float(overfull_precision), 1),
        'baseline_mae': round(float(mae_baseline), 2),
        'baseline_rmse': round(float(rmse_baseline), 2),
        'mae_improvement_pct': round(float((mae_baseline - mae_model) / mae_baseline * 100.0), 1),
        'actual_test_mean': round(float(test['fill_num'].mean()), 2),
        'predicted_test_mean': round(float(test['pred_fill'].mean()), 2)
    }

    return metrics, test
