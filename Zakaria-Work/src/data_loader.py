"""Validated pre-emptying observations. Raw files are never modified."""
from pathlib import Path
import holidays
import numpy as np
import pandas as pd

KEY = ['Location_id', 'material_type']
PROJECT_ROOT = Path(__file__).resolve().parents[1]
MATERIALS = ('brown', 'green', 'white')


def planning_day(value):
    day = pd.Timestamp(value)
    if pd.isna(day) or day.tzinfo is not None or day != day.normalize():
        raise ValueError('Use a timezone-free calendar date, not a timestamp.')
    return day


def historical_prefix(df, as_of=None, *, inclusive=True):
    """Inclusive review; morning dispatch explicitly uses inclusive=False."""
    if as_of is None:
        return df.copy()
    day = planning_day(as_of)
    return df.loc[df['date'].le(day) if inclusive else df['date'].lt(day)].copy()


def load_and_clean_data(csv_path='glass_fill_levels_anonymized_f.csv'):
    choices = [Path(csv_path), PROJECT_ROOT / csv_path, PROJECT_ROOT / 'PreZero' / csv_path]
    path = next((p for p in choices if p.is_file()), None)
    if path is None:
        raise FileNotFoundError(f'Cannot find {csv_path}')
    df = pd.read_csv(path, encoding='utf-8-sig', dtype=str, keep_default_na=False)
    df.columns = df.columns.str.strip().str.replace(chr(65279), '', regex=False)
    required = [*KEY, 'date', 'fill_level_perc']
    missing = set(required) - set(df.columns)
    if missing:
        raise ValueError(f'Missing columns: {sorted(missing)}')
    df = df[required].copy()
    for col in required:
        df[col] = df[col].str.strip()
    df['material_type'] = df['material_type'].str.lower()
    parsed = pd.to_datetime(df['date'], format='%Y-%m-%d', errors='coerce')
    strict_dates = parsed.notna() & parsed.dt.strftime('%Y-%m-%d').eq(df['date'])
    raw = df['fill_level_perc'].str.lower()
    overfull = raw.eq('overfull')
    numeric = pd.to_numeric(raw.where(~overfull), errors='coerce')
    valid_fill = overfull | (np.isfinite(numeric) & numeric.between(0, 100))
    valid = df['Location_id'].ne('') & df['material_type'].isin(MATERIALS) & strict_dates & valid_fill
    if not valid.all():
        rows = (np.flatnonzero(~valid.to_numpy()) + 2).tolist()
        raise ValueError(f'Invalid location, material, ISO date or fill at CSV lines {rows[:20]}')
    df['date'] = parsed
    df['is_overfull'] = overfull
    df['fill_num'] = numeric.astype(float)
    if df.duplicated([*KEY, 'date']).any():
        raise ValueError('Duplicate location/material/date readings; resolve explicitly.')
    df = df.sort_values([*KEY, 'date'], kind='stable').reset_index(drop=True)
    df['year_month'] = df['date'].dt.strftime('%Y-%m')
    df['day_name'] = df['date'].dt.day_name()
    df['day_of_week'] = df['date'].dt.day_of_week
    df['week_number'] = df['date'].dt.isocalendar().week
    calendar = holidays.Germany(subdiv='BW', years=sorted(set(df['date'].dt.year)))
    tags = {}
    for day in df['date'].unique():
        day = pd.Timestamp(day)
        name = calendar.get(day.date(), '')
        festive = (day.month == 12 and day.day >= 20) or (day.month == 1 and day.day <= 6)
        tags[day] = (bool(name), bool(name) or festive, name or ('Christmas / New Year window' if festive else 'Regular day'))
    df['is_public_holiday'] = df['date'].map(lambda d: tags[d][0]).astype(bool)
    df['is_holiday_window'] = df['date'].map(lambda d: tags[d][1]).astype(bool)
    df['holiday_name'] = df['date'].map(lambda d: tags[d][2])
    df['is_holiday'] = df['is_public_holiday']
    group = df.groupby(KEY, sort=False)
    df['prev_date'] = group['date'].shift()
    df['days_diff'] = (df['date'] - df['prev_date']).dt.days
    df['prev_fill'] = group['fill_num'].shift()
    df['fill_diff'] = df['fill_num'] - df['prev_fill']  # descriptive, not emptying detection
    df['cycle_fill_lower_bound'] = df['fill_num'].where(~df['is_overfull'], 100.0)
    df['cycle_is_censored'] = df['is_overfull'] | df['fill_num'].eq(100)
    df['cycle_rate_pct_per_day'] = df['cycle_fill_lower_bound'] / df['days_diff'].where(df['days_diff'] > 0)
    return df


def get_latest_readings(df, as_of=None, *, inclusive=True):
    sub = historical_prefix(df, as_of, inclusive=inclusive)
    return sub.sort_values('date', kind='stable').drop_duplicates(KEY, keep='last').reset_index(drop=True)


def collection_summary(df, as_of=None):
    return historical_prefix(df, as_of).groupby('material_type').agg(
        collections=('date', 'size'), numeric_readings=('fill_num', 'count'),
        mean_numeric_fill=('fill_num', 'mean'), overfull_count=('is_overfull', 'sum'),
        median_interval_days=('days_diff', 'median'),
    ).reset_index()
