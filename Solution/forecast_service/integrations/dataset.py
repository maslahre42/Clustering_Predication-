"""Kaise's strict ingestion boundary, adapted to request-local CSV and legacy snapshots."""
import csv
import hashlib
import io
import json
from dataclasses import asdict, replace
import numpy as np
import pandas as pd
from .kaise.data.loader import load_glass_fill_rows, _validate_data_row, _duplicate_key_error
from .kaise.data.schema import ReadingRecord
from .kaise.analytics.series_features import compute_series_features
from .kaise.analytics.grouping import cluster_or_tier

MAX_CSV_BYTES = 2_000_000


class DatasetValidationError(ValueError):
    def __init__(self, errors, warnings=()):
        super().__init__('Dataset rejected. Resolve the reported rows; no rows were silently removed.')
        self.errors = errors
        self.warnings = list(warnings)


def source(payload):
    """Validate before modeling. Imported data never writes or mixes with SQLite."""
    if payload.get('csv') is not None:
        value = payload['csv']
        if not isinstance(value,str) or len(value.encode('utf-8')) > MAX_CSV_BYTES:
            raise DatasetValidationError([dict(rule_id='size',row_number=0,message='CSV must be at most 2 MB.')])
        try:
            rows = list(csv.reader(io.StringIO(value.lstrip('\ufeff')),strict=True))
        except csv.Error as error:
            raise DatasetValidationError([dict(rule_id='csv',row_number=0,message=str(error))])
        result = load_glass_fill_rows(rows)
        if result.errors:
            raise DatasetValidationError([asdict(e) for e in result.errors],[asdict(w) for w in result.warnings])
        observations = [dict(locationId=r.location_id,material=r.material_type,date=r.date.isoformat(),
                             fillLevel='overfull' if r.is_overfull else str(r.fill_level_pct)) for r in result.dataset.readings]
        return observations, [asdict(w) for w in result.warnings], 'uploaded-csv'
    observations = [r for r in payload['observations'] if r['date'] <= payload['asOf']]
    errors, warnings, seen = [], [], {}
    for number,row in enumerate(observations,1):
        cells = [row['locationId'],row['material'],row['date'],str(row['fillLevel'])]
        row_errors,row_warnings,_,key_info = _validate_data_row(cells,number)
        # Existing legacy unknown observations remain evidence of emptying, not made-up numbers.
        if cells[3].strip().lower() in ('unknown','','none','null'):
            row_errors = [e for e in row_errors if e.rule_id not in ('R2','R5')]
            if not all(cells[:3]):
                row_errors += _validate_data_row(cells[:3]+['0'],number)[0]
            warnings.append(dict(rule_id='R8',row_number=number,message='Unknown legacy fill retained as an emptying observation; it supplies no numeric rate.'))
        errors.extend(asdict(e) for e in row_errors)
        warnings.extend(asdict(w) for w in row_warnings)
        if key_info:
            key,fill = key_info
            duplicate = _duplicate_key_error(seen,key,fill,number)
            if duplicate: errors.append(asdict(duplicate))
            seen[key] = fill
    if errors: raise DatasetValidationError(errors,warnings)
    return observations,warnings,'sqlite-snapshot'


def evidence(df,payload):
    """Kaise's clustering gates applied to reset-aware cycle-rate features."""
    _,warnings,kind = source(payload)
    records = [ReadingRecord(r.site,r.material,r.date.date(),None if r.overfull else int(r.fill),bool(r.overfull))
               for r in df.itertuples() if r.overfull or pd.notna(r.fill)]
    features = compute_series_features(records)
    cycles = df.copy()
    cycles['gap'] = cycles.groupby('container').date.diff().dt.days
    cycles['cycle_rate'] = cycles['fill']/cycles.gap.where(cycles.gap>0)
    rates = cycles.groupby(['site','material']).cycle_rate.median()
    by_bin = cycles.groupby(['site','material'])
    counts = by_bin.size()
    overfull_share = by_bin.overfull.mean()
    numeric_full_share = cycles.assign(numeric_full=cycles['fill'].eq(100) & ~cycles.overfull).groupby(['site','material']).numeric_full.mean()
    features = [replace(f,n_readings=int(counts[(f.location_id,f.material_type)]),
                        overfull_share=float(overfull_share[(f.location_id,f.material_type)]),
                        share_at_100=float(numeric_full_share[(f.location_id,f.material_type)]),
                        median_rate_pct_per_day=None if pd.isna(rates.get((f.location_id,f.material_type))) else float(rates[(f.location_id,f.material_type)])) for f in features]
    grouped = cluster_or_tier(features)
    labels = [dict(locationId=k[0],material=k[1],group=v) for k,v in sorted(grouped.labels.items())]
    represented = set(grouped.labels)
    for site,material in sorted(set(zip(df.site,df.material))-represented):
        labels.append(dict(locationId=site,material=material,group='insufficient_history'))
    canonical = sorted((r.site,r.material,r.date.isoformat(),None if pd.isna(r.fill) else float(r.fill),bool(r.overfull)) for r in df.itertuples())
    fingerprint = hashlib.sha256(json.dumps(canonical,separators=(',',':')).encode()).hexdigest()
    profile_rows = [asdict(p) for p in grouped.profiles]
    unknown_only = len(set(zip(df.site,df.material))-represented)
    if unknown_only:
        existing = next((p for p in profile_rows if p['label']=='insufficient_history'),None)
        if existing: existing['n_series'] += unknown_only
        else: profile_rows.append(dict(label='insufficient_history',n_series=unknown_only,feature_medians={}))
    groups = dict(method=grouped.method,gate=grouped.gate,silhouetteByK=grouped.silhouette_by_k,
                  eligible=grouped.n_eligible,insufficient=sum(x['group']=='insufficient_history' for x in labels),
                  profiles=profile_rows,labels=labels,
                  note='Kaise’s interpretability gates; reset-aware cycle rates replace consecutive fill differences. Descriptive groups do not determine dispatch.')
    return dict(source=kind,fingerprint=fingerprint,rows=len(df),bins=int(df.container.nunique()),
                dateMin=None if df.empty else df.date.min().date().isoformat(),dateMax=None if df.empty else df.date.max().date().isoformat(),
                unknown=int(df.fill.isna().sum()),overfull=int(df.overfull.sum()),warnings=warnings,grouping=groups)
