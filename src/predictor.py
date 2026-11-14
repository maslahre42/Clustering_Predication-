import pandas as pd
import numpy as np

def predict_container_demands(
    profiles_df: pd.DataFrame,
    days_ahead: int = 2,
    holiday_multiplier: float = 1.0,
    container_volume_m3: float = 2.5,
    glass_density_kg_m3: float = 380.0
) -> pd.DataFrame:
    """
    Forecasts future container fill levels, volume, and weight demands.
    Classifies urgency into Urgent (>=80%), Opportunistic (60-79%), and Safe (<60%).
    """
    df_pred = profiles_df.copy()
    
    # Predict fill level
    projected_growth = df_pred['daily_fill_velocity'] * days_ahead * holiday_multiplier
    df_pred['predicted_fill_perc'] = (df_pred['current_fill_perc'] + projected_growth).clip(upper=110.0).round(1)
    
    # Calculate physical demand
    fill_ratio = df_pred['predicted_fill_perc'] / 100.0
    df_pred['demand_volume_m3'] = (fill_ratio * container_volume_m3).round(2)
    df_pred['demand_weight_kg'] = (df_pred['demand_volume_m3'] * glass_density_kg_m3).round(1)
    
    # Classification
    def categorize_urgency(val):
        if val >= 80.0:
            return 'Urgent (>=80%)'
        elif val >= 60.0:
            return 'Opportunistic (60-79%)'
        else:
            return 'Safe (<60%)'
            
    df_pred['urgency_status'] = df_pred['predicted_fill_perc'].apply(categorize_urgency)
    return df_pred
