"""Rolling chronological evaluation at actual collection dates, not a digital twin."""
import numpy as np
import pandas as pd

from .clustering import extract_container_profiles
from .data_loader import KEY, planning_day
from .predictor import predict_container_demands


def evaluate_forecasts(df, test_start='2026-04-01', threshold=80.0):
    """All features come strictly before each target day; overfull is not numeric truth.

    Earlier test-period visits become known at subsequent decisions (rolling evaluation).
    This scores observed visits, not counterfactual daily occupancy or route savings.
    """
    start = planning_day(test_start)
    cases = []
    for day, truth in df.loc[df['date'].ge(start)].groupby('date', sort=True):
        profiles = extract_container_profiles(df, as_of=day, inclusive=False)
        forecasts = predict_container_demands(profiles, planning_date=day, days_ahead=0)
        forecasts = forecasts[[*KEY, 'predicted_fill_perc', 'last_pre_emptying_fill_perc']]
        rows = truth[[*KEY, 'date', 'fill_num', 'is_overfull']].merge(forecasts, on=KEY, how='left', validate='one_to_one')
        cases.append(rows)
    columns = [*KEY, 'date', 'fill_num', 'is_overfull', 'predicted_fill_perc', 'last_pre_emptying_fill_perc']
    cases = pd.concat(cases, ignore_index=True) if cases else pd.DataFrame(columns=columns)
    metrics = []
    # Use the same common numeric rows for a fair numerical comparison.
    common = cases['fill_num'].notna() & cases['predicted_fill_perc'].notna() & cases['last_pre_emptying_fill_perc'].notna()
    for name, col in [('cycle_median_lower_bound', 'predicted_fill_perc'), ('last_pre_emptying_reading', 'last_pre_emptying_fill_perc')]:
        error = cases.loc[common, col] - cases.loc[common, 'fill_num']
        available = cases[col].notna()
        actual_positive = cases['is_overfull'].eq(True) | cases['fill_num'].ge(threshold)
        predicted_positive = cases[col].ge(threshold)
        metrics.append(dict(method=name, target_cases=len(cases), available_forecasts=int(available.sum()),
            common_numeric_cases=int(common.sum()), overfull_truths=int(cases['is_overfull'].sum()),
            mae_pp=float(error.abs().mean()) if len(error) else None,
            rmse_pp=float(np.sqrt((error**2).mean())) if len(error) else None,
            true_positive=int((available & actual_positive & predicted_positive).sum()),
            false_positive=int((available & ~actual_positive & predicted_positive).sum()),
            false_negative=int((available & actual_positive & ~predicted_positive).sum()),
            true_negative=int((available & ~actual_positive & ~predicted_positive).sum())))
    return pd.DataFrame(metrics), cases
