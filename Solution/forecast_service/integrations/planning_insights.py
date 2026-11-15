"""Cutoff-safe planning explanations and explicit operating-cost arithmetic."""
import math
from decimal import Decimal, ROUND_HALF_UP
import numpy as np
import pandas as pd


def operating_cost(distance_km, trucks, settings):
    per_km, fixed = settings.get('costPerKmEuro', 0), settings.get('fixedTruckCostEuro', 0)
    if any(not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 for value in (per_km, fixed, trucks)):
        raise ValueError('Operating costs and scheduled truck counts must be finite and nonnegative.')
    if distance_km is not None and (not math.isfinite(distance_km) or distance_km < 0):
        raise ValueError('Street kilometers must be finite and nonnegative.')
    configured = per_km > 0 or fixed > 0
    cents = lambda value: value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    money = lambda value: float(cents(value))
    variable_amount = None if per_km > 0 and distance_km is None else Decimal(str(distance_km or 0)) * Decimal(str(per_km))
    fixed_amount = Decimal(str(trucks)) * Decimal(str(fixed))
    return dict(configured=configured,partial=configured and (per_km == 0 or fixed == 0),
        variableEuro=money(variable_amount) if configured and variable_amount is not None else None,
        fixedEuro=money(fixed_amount) if configured else None,
        totalEuro=money(cents(variable_amount) + cents(fixed_amount)) if configured and variable_amount is not None else None,
        costPerKmEuro=per_km,fixedTruckCostEuro=fixed,trucks=trucks,distanceKm=distance_km)


def fill_timing(df, model, intervals, as_of):
    """Time-to-full quantiles from the existing fitted model, relative to the cutoff.

    The model's time estimate approximates the reset-month seasonal effect.
    Every input is already cutoff bounded. Sparse bins retain explicit no-estimate reasons.
    """
    if df.empty:
        return []
    last = df.groupby('container',sort=True).tail(1)
    own_cycles = intervals.groupby('container').size().to_dict() if 'container' in intervals else {}
    censored = intervals.groupby('container').censored.sum().to_dict() if 'container' in intervals else {}
    if model is not None:
        times = [model.days_to_full(last.container,last.date,q) for q in (.1,.5,.9)]
    else:
        times = [np.full(len(last),np.nan)] * 3
    result=[]
    for index, row in enumerate(last.itertuples()):
        age=(pd.Timestamp(as_of)-row.date).days
        early,median,late=(float(values[index]) for values in times)
        reason = 'no_completed_cycles' if not own_cycles.get(row.container) else None
        if reason is None and (not all(math.isfinite(t) and 0 <= t <= 3650 for t in (early,median,late)) or model is None):
            reason='outside_model_range'
        result.append(dict(locationId=row.site,material=row.material,lastEmptied=row.date.date().isoformat(),
            historyCycles=int(own_cycles.get(row.container,0)),censoredCycles=int(censored.get(row.container,0)),
            medianDaysUntilFull=None if reason else round(median-age,1),
            earlyDaysUntilFull=None if reason else round(early-age,1),lateDaysUntilFull=None if reason else round(late-age,1),
            predictedFullDate=None if reason else (row.date+pd.Timedelta(days=math.ceil(median))).date().isoformat(),reason=reason))
    return result
