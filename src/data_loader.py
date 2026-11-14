import os
import pandas as pd
import numpy as np
import holidays
from typing import Optional

def load_and_clean_data(csv_path: str = "glass_fill_levels_anonymized_f.csv") -> pd.DataFrame:
    """
    Loads, cleans, and enriches the glass container fill level dataset.
    Adds calendar features and Baden-Württemberg public holidays.
    """
    if not os.path.exists(csv_path):
        alt_path = os.path.join("PreZero", csv_path)
        if os.path.exists(alt_path):
            csv_path = alt_path
        else:
            raise FileNotFoundError(f"Cannot find dataset at {csv_path} or {alt_path}")

    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    df.columns = [c.strip().replace('\ufeff', '') for c in df.columns]
    
    # Parse date
    df['date'] = pd.to_datetime(df['date'])
    
    # Overfull and numeric fill
    df['is_overfull'] = df['fill_level_perc'].astype(str).str.strip().str.lower() == 'overfull'
    df['fill_num'] = df['fill_level_perc'].apply(
        lambda x: 110.0 if str(x).strip().lower() == 'overfull' else float(x)
    )
    
    # Sort chronologically
    df = df.sort_values(by=['Location_id', 'material_type', 'date']).reset_index(drop=True)
    
    # Calendar features
    df['year_month'] = df['date'].dt.to_period('M')
    df['day_name'] = df['date'].dt.day_name()
    df['day_of_week'] = df['date'].dt.dayofweek
    df['week_number'] = df['date'].dt.isocalendar().week
    
    # Baden-Württemberg Holiday & Festive Season Integration
    de_bw = holidays.Germany(prov='BW', years=[2025, 2026])
    
    def get_holiday_tag(dt):
        d = dt.date()
        # Direct statutory holiday
        if d in de_bw:
            return True, de_bw[d]
        # Christmas / Silvester / New Year festive period (peak glass consumption)
        if (d.month == 12 and d.day >= 20) or (d.month == 1 and d.day <= 6):
            return True, 'Christmas / New Year Season'
        # Proximity within +/-3 days of any Baden-Württemberg statutory holiday
        for h_date, h_name in de_bw.items():
            diff = (d - h_date).days
            if 0 < diff <= 3:
                return True, f'Post-{h_name} (+{diff}d)'
            elif -3 <= diff < 0:
                return True, f'Pre-{h_name} ({diff}d)'
        return False, 'Standard Regular Day'

    h_tags = df['date'].apply(get_holiday_tag)
    df['is_holiday'] = [h[0] for h in h_tags]
    df['holiday_name'] = [h[1] for h in h_tags]
    
    # Sequential intervals per container
    df['prev_date'] = df.groupby(['Location_id', 'material_type'])['date'].shift(1)
    df['prev_fill'] = df.groupby(['Location_id', 'material_type'])['fill_num'].shift(1)
    df['days_diff'] = (df['date'] - df['prev_date']).dt.days
    df['fill_diff'] = df['fill_num'] - df['prev_fill']
    
    return df

def get_latest_readings(df: pd.DataFrame) -> pd.DataFrame:
    """Returns the most recent observation for each container (Location_id, material_type)."""
    latest = df.sort_values('date').groupby(['Location_id', 'material_type']).last().reset_index()
    return latest
