#!/usr/bin/env python3
"""Explicit, backed-up demo coordinate replacement; collection history is immutable."""
import argparse
import datetime
import hashlib
import json
import math
from pathlib import Path
import sqlite3


def history_digest(connection):
    digest = hashlib.sha256()
    for row in connection.execute('SELECT * FROM raw_data ORDER BY Location_id, material_type, date, fill_level_perc'):
        digest.update((json.dumps(row, ensure_ascii=False) + '\n').encode())
    return digest.hexdigest()


def replace_coordinates(database, manifest_path, backup_directory):
    manifest = json.loads(Path(manifest_path).read_text())
    sites = manifest['sites']
    coordinates = [(site['latitude'], site['longitude']) for site in sites]
    if len(set(coordinates)) != len(sites) or not sites:
        raise ValueError('Sites must have distinct coordinates.')
    if any(not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180 for lat, lon in coordinates):
        raise ValueError('Invalid WGS84 coordinates.')
    backup_directory = Path(backup_directory)
    backup_directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup_path = backup_directory / f'sql-before-karlsruhe-{stamp}.db'
    audit_path = backup_directory / f'karlsruhe-coordinate-update-{stamp}.json'
    with sqlite3.connect(Path(database).resolve().as_uri() + '?mode=rw', uri=True) as connection:
        connection.execute('BEGIN IMMEDIATE')
        before = connection.execute('SELECT location_id, latitude, longitude, is_synthetic FROM locations ORDER BY location_id').fetchall()
        if len(before) != len(sites):
            raise ValueError('Site count must match existing UUID count.')
        history_before = history_digest(connection)
        # A separate read connection can back up the unchanged source while this
        # connection holds the writer lock, preventing concurrent modifications.
        with sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True) as source, sqlite3.connect(backup_path) as backup:
            source.backup(backup)
            assert backup.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            assert history_digest(backup) == history_before
            assert backup.execute('SELECT location_id, latitude, longitude, is_synthetic FROM locations ORDER BY location_id').fetchall() == before
        assignments = [dict(location_id=old[0], previous=dict(latitude=old[1], longitude=old[2], is_synthetic=old[3]), **site) for old, site in zip(before, sites)]
        connection.executemany('UPDATE locations SET latitude=?, longitude=?, is_synthetic=1 WHERE location_id=?', [(r['latitude'], r['longitude'], r['location_id']) for r in assignments])
        expected = [(r['location_id'], r['latitude'], r['longitude'], 1) for r in assignments]
        assert connection.execute('SELECT location_id, latitude, longitude, is_synthetic FROM locations ORDER BY location_id').fetchall() == expected
        assert history_digest(connection) == history_before
        assert connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        audit = dict(timestamp=stamp, backup=str(backup_path), history_sha256=history_before, manifest_sha256=hashlib.sha256(Path(manifest_path).read_bytes()).hexdigest(), assignment=manifest['assignment'], assignments=assignments)
        audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
        connection.commit()
    return audit_path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True, type=Path)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--backup-directory', required=True, type=Path)
    parser.add_argument('--apply', action='store_true', help='Explicitly authorize writing coordinates.')
    args = parser.parse_args()
    if not args.apply:
        parser.error('Nothing changed: --apply is required.')
    print(replace_coordinates(args.database, args.manifest, args.backup_directory))
