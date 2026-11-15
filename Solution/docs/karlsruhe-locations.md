# Karlsruhe demo geography

Applied at the user's explicit request on 15 November 2026. This data replacement overrides the usual read-only source-database rule for this operation only; application requests still open SQLite read-only.

The 449 existing location UUIDs now have 449 distinct mapped glass-container positions. All 11,701 collection observations, UUIDs, materials, fill values, dates and database schema were preserved. All assignments remain `is_synthetic=1`: real site coordinates do not establish that the supplied collection history belongs to those sites.

## Sources and selection

- **314 city sites:** [Stadt Karlsruhe official glass-container dataset](https://transparenz.karlsruhe.de/dataset/points-of-interest-entsorgungseinrichtungen). Retrieved GeoJSON snapshot: [source-city.geojson](../data/karlsruhe/source-city.geojson). Attribution: Stadt Karlsruhe, Datenlizenz Deutschland Namensnennung 2.0. No modifications to source point positions.
- **27 city districts:** [official Stadtteile boundaries](https://transparenz.karlsruhe.de/dataset/stadtteile), CC0, Stadt Karlsruhe. City points were assigned by point-in-polygon, including polygon holes; each point matched exactly one district.
- **135 surrounding sites:** [AWB Landkreis Karlsruhe public directory](https://www.awb-landkreis-karlsruhe.de/start/entsorgen/standorte+_+oeffnungszeiten.html), Altglascontainer. Retrieved from its linked public [location service](https://waste.awb-landkreis-karlsruhe.de/WasteManagementKarlsruheHaushalteBlank/WasteManagementServlet?SubmitAction=Entsein&InFrameMode=TRUE). Municipal/subdistrict names and coordinates come directly from its map markers. No geocoding or artificial point offsets were required. No open-data reuse license was identified for this directory; retain attribution and check reuse terms before redistributing its snapshot beyond this local demo.

Preserve all city points. Sort 179 retrieved candidates from nine nearby Landkreis municipalities by straight-line distance to the demo centre (49.0094, 8.4044), breaking ties by source ID. Exclude regional candidates within 75 metres of any selected point and stop at 449 total. This selects the nearest eligible sites **among the retrieved candidates**, not a complete inventory of the Landkreis. The farthest selected point is 12.245 km from the centre; this is a selection radius, not a driving-distance claim. Public routes still use OSRM street distances.

| Municipality | Selected sites |
| --- | ---: |
| Karlsruhe | 314 |
| Ettlingen | 42 |
| Eggenstein-Leopoldshafen | 23 |
| Pfinztal | 20 |
| Rheinstetten | 19 |
| Stutensee | 17 |
| Waldbronn | 6 |
| Weingarten | 5 |
| Karlsbad | 2 |
| Linkenheim-Hochstetten | 1 |
| **Total** | **449** |

The [selection manifest](../data/karlsruhe/sites.json) retains names, coordinates, district, municipality and source. [UUID assignments CSV](../data/karlsruhe/location-assignments.csv) gives the exact database mapping, deterministically assigned by existing UUID sort order. District/address metadata is in these provenance files; the database's original `locations` schema remains unchanged.

## Application defaults

City labels, initial map centre, manual preview depot and public proposal defaults now use Karlsruhe. Yard and disposal both default to the same demo point at (49.0094, 8.4044), avoiding an invented disposal facility or a return to Heilbronn. Enter actual operating points under Collection settings. Neither is claimed to be a verified truck yard or glass processing facility. No Karlsruhe collection measurements were invented.

## Backup and verification

Backup created and integrity checked before writing: `backups/sql-before-karlsruhe-20261115T042417708084Z.db`. Full audit, including old/new positions and unchanged history SHA256: `backups/karlsruhe-coordinate-update-20261115T042417708084Z.json`.

The migration acquired a writer lock, verified an independent SQLite backup, updated coordinates inside one transaction, and checked the exact resulting mapping, unchanged history digest and SQLite integrity before committing. Automated tests exercise full-history/schema preservation, backup data, deterministic assignments and rejection of invalid/duplicate coordinates or mismatched counts without modifying the database.

To restore the previous Heilbronn dataset, stop the application and restore the backup database. Retain its corresponding Heilbronn app defaults as well if reverting the whole demo geography. Backups are local and excluded from source handoff archives.
