import pandas as pd
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error
from typing import Optional, Union, Dict, Tuple

def predict_container_demands(
    profiles_df: pd.DataFrame,
    days_ahead: int = 2,
    reference_date: Optional[Union[str, pd.Timestamp]] = None,
    days_since_last_collection: Optional[Union[int, float, pd.Series]] = None,
    residual_fill_perc: float = 0.0,
    holiday_multiplier: float = 1.0,
    container_volume_m3: float = 2.5,
    glass_density_kg_m3: float = 380.0
) -> pd.DataFrame:
    """
    Forecasts future container fill levels, volume (m³), and weight (kg) demands.
    
    Operational Reality:
    Every historical record in the PreZero dataset represents an emptying visit that reset
    the container back to residual_fill_perc (default 0.0%). Therefore, predicting the fill
    level at future time t + Δt should NOT add new growth onto an already-recorded pre-collection
    fill level!
    
    Instead, the forecasted fill level since last collection is:
        Fill_pred_i(Δt) = min(110%, residual_fill_perc + v_i * Δt * S_holiday)
    where:
        - v_i is the container's true daily fill velocity (%/day)
        - Δt is the days elapsed since the last collection visit (+ days_ahead lookahead)
        - S_holiday is the holiday multiplier (e.g. 1.25 during peak seasons, 1.0 otherwise)
        - residual_fill_perc is the post-emptying residual waste (default 0.0%)
        
    Classifies urgency into:
        - Urgent (>=80%)
        - Opportunistic (60-79%)
        - Safe (<60%)
    """
    df_pred = profiles_df.copy()
    
    # Compute elapsed days since last collection (Δt)
    if days_since_last_collection is not None:
        if isinstance(days_since_last_collection, (int, float)):
            delta_t = float(days_since_last_collection) + float(days_ahead)
        else:
            delta_t = days_since_last_collection + float(days_ahead)
    elif 'last_reading_date' in df_pred.columns:
        last_dates = pd.to_datetime(df_pred['last_reading_date'])
        ref_dt = pd.to_datetime(reference_date) if reference_date is not None else last_dates.max()
        elapsed_days = (ref_dt - last_dates).dt.days
        delta_t = (elapsed_days + days_ahead).clip(lower=0)
    else:
        delta_t = max(days_ahead, 0)
        
    df_pred['days_since_last_collection'] = delta_t

    # Physics-grounded accumulation from residual fill
    projected_growth = df_pred['daily_fill_velocity'] * delta_t * holiday_multiplier
    df_pred['predicted_fill_perc'] = (residual_fill_perc + projected_growth).clip(upper=110.0).round(1)
    
    # Calculate physical demand (volume in m³, weight in kg)
    fill_ratio = df_pred['predicted_fill_perc'] / 100.0
    df_pred['demand_volume_m3'] = (fill_ratio * container_volume_m3).round(2)
    df_pred['demand_weight_kg'] = (df_pred['demand_volume_m3'] * glass_density_kg_m3).round(1)
    
    # Operational urgency classification for dispatch routing
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
) -> Tuple[Dict[str, float], pd.DataFrame]:
    """
    Validates fill level predictions against historical data using a chronological train/test split.
    
    Protocol:
      1. Filter consecutive collection intervals (0 < days_diff <= 180).
      2. Chronologically sort by date and partition into train (first 80%) and holdout test (final 20%).
      3. Learn per-location fill velocity v_i = (fill_num - residual) / days_diff on the training set.
      4. Forecast fill levels on the unseen holdout test set using:
         Fill_pred = min(110%, residual + v_i * days_diff * (holiday_multiplier if is_holiday else 1.0))
      5. Compute MAE, RMSE, and error reduction compared to baseline.
    """
    sub = df.copy()
    sub['date'] = pd.to_datetime(sub['date'])
    if material_filter:
        sub = sub[sub['material_type'] == material_filter].copy()

    sub = sub.sort_values('date').reset_index(drop=True)
    valid = sub[(sub['days_diff'] > 0) & (sub['days_diff'] <= 180)].copy()

    split_idx = int(len(valid) * train_ratio)
    split_date = valid.iloc[split_idx]['date']
    
    train = valid[valid['date'] < split_date].copy()
    test = valid[valid['date'] >= split_date].copy()

    # Train velocity estimation
    train['daily_vel'] = (train['fill_num'] - residual_fill_perc) / train['days_diff']
    train_pos = train[train['daily_vel'] > 0]
    vel_by_loc = train_pos.groupby('Location_id')['daily_vel'].median()
    global_median_vel = train_pos['daily_vel'].median() if len(train_pos) > 0 else 2.5

    # Test holdout evaluation
    test['pred_vel'] = test['Location_id'].map(vel_by_loc).fillna(global_median_vel)
    h_mult = test['is_holiday'].apply(lambda h: holiday_multiplier if h else 1.0)
    test['pred_fill'] = (residual_fill_perc + test['pred_vel'] * test['days_diff'] * h_mult).clip(upper=110.0)

    # Baseline: Naive cumulative addition (adding onto pre-collection fill level)
    train_old = train.copy()
    train_old_pos = train_old[(train_old['fill_diff'] >= 0) & (train_old['days_diff'] > 0)]
    old_vel_by_loc = (train_old_pos['fill_diff'] / train_old_pos['days_diff']).groupby(train_old_pos['Location_id']).median()
    test['old_vel'] = test['Location_id'].map(old_vel_by_loc).fillna(0.65)
    test['old_pred_fill'] = (test['prev_fill'] + test['old_vel'] * test['days_diff']).clip(upper=110.0)

    mae_model = mean_absolute_error(test['fill_num'], test['pred_fill'])
    rmse_model = np.sqrt(mean_squared_error(test['fill_num'], test['pred_fill']))
    
    mae_baseline = mean_absolute_error(test['fill_num'], test['old_pred_fill'])
    rmse_baseline = np.sqrt(mean_squared_error(test['fill_num'], test['old_pred_fill']))

    metrics = {
        'train_samples': len(train),
        'test_samples': len(test),
        'train_date_range': f"{train['date'].min().strftime('%Y-%m-%d')} to {train['date'].max().strftime('%Y-%m-%d')}",
        'test_date_range': f"{test['date'].min().strftime('%Y-%m-%d')} to {test['date'].max().strftime('%Y-%m-%d')}",
        'mae': round(mae_model, 2),
        'rmse': round(rmse_model, 2),
        'baseline_mae': round(mae_baseline, 2),
        'baseline_rmse': round(rmse_baseline, 2),
        'mae_improvement_pct': round((mae_baseline - mae_model) / mae_baseline * 100, 1),
        'actual_test_mean': round(test['fill_num'].mean(), 2),
        'predicted_test_mean': round(test['pred_fill'].mean(), 2)
    }

    return metrics, test
