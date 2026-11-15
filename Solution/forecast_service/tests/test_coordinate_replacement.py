"""Coordinate-only migration preserves history and can be restored from its backup."""
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest

spec = importlib.util.spec_from_file_location('coordinate_replacement', Path(__file__).resolve().parents[2] / 'scripts/replace-location-coordinates.py')
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


def fixture(tmp_path):
    db = tmp_path / 'source.db'
    with sqlite3.connect(db) as connection:
        connection.executescript('CREATE TABLE locations(location_id TEXT PRIMARY KEY, latitude REAL, longitude REAL, is_synthetic INTEGER); CREATE TABLE raw_data(Location_id TEXT, material_type TEXT, date TEXT, fill_level_perc TEXT);')
        connection.executemany('INSERT INTO locations VALUES(?,?,?,?)', [('B',49,9,0),('A',48,8,1)])
        connection.executemany('INSERT INTO raw_data VALUES(?,?,?,?)', [('A','brown glass','2026-09-30','overfull'),('B','white glass','2026-09-29','unknown'),('B','white glass','2026-09-30','100')])
    manifest = tmp_path / 'sites.json'
    sites = [dict(latitude=49.01,longitude=8.4,name='First'),dict(latitude=49.02,longitude=8.5,name='Second')]
    manifest.write_text(json.dumps(dict(assignment='Synthetic demo',sites=sites)))
    return db, manifest


def test_replacement_preserves_uuid_history_and_verified_backup(tmp_path):
    db, manifest = fixture(tmp_path)
    audit_path = migration.replace_coordinates(db, manifest, tmp_path / 'backups')
    audit = json.loads(audit_path.read_text())
    with sqlite3.connect(db) as current, sqlite3.connect(audit['backup']) as backup:
        assert migration.history_digest(current) == migration.history_digest(backup) == audit['history_sha256']
        assert current.execute('SELECT * FROM locations ORDER BY location_id').fetchall() == [('A',49.01,8.4,1),('B',49.02,8.5,1)]
        assert backup.execute('SELECT * FROM locations ORDER BY location_id').fetchall() == [('A',48,8,1),('B',49,9,0)]
        assert current.execute("SELECT name,sql FROM sqlite_master ORDER BY name").fetchall() == backup.execute("SELECT name,sql FROM sqlite_master ORDER BY name").fetchall()
    assert [row['name'] for row in audit['assignments']] == ['First','Second']


@pytest.mark.parametrize('sites', [[], [dict(latitude=49,longitude=8)], [dict(latitude=99,longitude=8),dict(latitude=49,longitude=8)], [dict(latitude=49,longitude=8)]*2])
def test_invalid_manifest_never_changes_database(tmp_path, sites):
    db, manifest = fixture(tmp_path)
    original = db.read_bytes()
    manifest.write_text(json.dumps(dict(assignment='Synthetic',sites=sites)))
    with pytest.raises(ValueError):
        migration.replace_coordinates(db, manifest, tmp_path / 'backups')
    assert db.read_bytes() == original
