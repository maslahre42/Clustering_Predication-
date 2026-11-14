# 449 synthetic locations: Heilbronn and the nearest surrounding towns

**Applied at the user's request on 2026-11-14T13:11:21.830249+00:00.** All 449 existing location UUIDs now use the reviewed coordinates. All 11,701 collection observations and the database schema were preserved. Every assignment remains `is_synthetic = 1` because its relationship to a mapped glass-container site is invented.

A full database backup was created and verified **before** the update: [original database backup](../backups/sql-before-regional-locations-20261114T131121740554Z.db). The [application audit](../backups/location-update-20261114T131121740554Z.json) records original and new positions, coordinate provenance, timestamps and database hashes. Integrity checks passed for the backup and updated database. The update was committed only after its results matched the reviewed proposal and collection history was verified unchanged.

The SQL below remains a **rollback preview** for inspection; the authorized update was applied separately in a verified transaction. The ten-minute driving target and residential suitability remain unverified as described below.

## Selected geography

The proposed layout contains:

- **109 reference sites in Heilbronn**, retrieved from your official map's `altglascontainerstandorte` layer.
- **340 additional mapped glass sites in surrounding towns and cities**, selected outward by distance from Heilbronn. No artificial offsets or additional street-label positions are used.
- **449 distinct positions**, spanning 53 municipality labels in the retrieved data. These are points, not 449 districts. The outermost selected point is approximately **28.51 km** from the center of your map view.

The center is the view position from [your official map link](https://karten.heilbronn.de/heilbronn/index.php?lang=de&zl=33&x=515975.5&y=5443108&bl=stadtplan&bo=1&lo=1&layers=altglascontainerstandorte&service=heilbronn): EPSG:25832 coordinates `(515975.5, 5443108)`, converted to approximately `(49.14059188, 9.21903326)` in latitude/longitude. This is the selection center, not a confirmed collection depot.

Nearby sources include Neckarsulm, Flein, Weinsberg, Leingarten, Talheim, Untergruppenbach, Bad Friedrichshall and Bad Wimpfen. Expanding farther adds sites around Brackenheim, Obersulm, Bad Rappenau, Eppingen, Öhringen, Mosbach, Backnang and other surrounding places, until there are enough distinct candidates.

## Data and selection method

The Heilbronn coordinates come from the [official point feed](https://karten.heilbronn.de/heilbronn/mod_poi/getpoijson.php?qidstr=altglascontainerstandorte&service=heilbronn&bbox=490000,5420000,530000,5460000). Its 109-point response is a retrieved layer snapshot, not proof that exactly 109 containers exist in the city. Original UTM coordinates are recorded as `source_reference` for those points.

Additional coordinates come from public town-level maps on Containerstandorte, such as [Neckarsulm](https://containerstandorte.de/glascontainer/neckarsulm), [Weinsberg](https://containerstandorte.de/glascontainer/weinsberg) and [Bad Wimpfen](https://containerstandorte.de/glascontainer/bad-wimpfen). These are third-party map listings, not exports from the official Heilbronn map. The site describes its inputs as OpenStreetMap and municipal data; individual regional entries have not been independently confirmed with municipal inventories. All used source-page URLs are embedded in the SQL. OpenStreetMap contributors retain attribution for OSM-derived inputs.

Selection was prepared as follows, from snapshots retrieved on 2026-11-14:

1. Preserve all 109 official Heilbronn reference sites.
2. Use the public town index to find nearby available glass-map pages. Retrieve their points and retain entries marked with a glass type.
3. Sort regional candidate points by straight-line distance from the map center, using their source IDs to break ties. Skip entries labelled Heilbronn to avoid duplicating the official city layer.
4. Reject a regional candidate within **75 metres** of any already selected point, to reduce duplicate representations of one container site. Existing official Heilbronn sites are retained as provided.
5. Stop when the total reaches 449, then assign local point IDs from nearest to farthest. The resulting maximum radius is about 28.51 km. This is the nearest eligible selection **among the retrieved candidates**, not a guarantee of a complete regional inventory or the globally smallest possible radius.

UUIDs are assigned deterministically by their existing sort order. Their previous coordinates are synthetic, so that ordering does not imply a recovered historical mapping. All glass materials at a UUID continue to share its single location; observations are not moved between UUIDs.

Mapped glass sites give a more plausible settlement pattern than random coordinates. The retrieved point feeds do not establish residential land use or suitability for a particular collection vehicle. The layout therefore follows neighbourhood collection-site evidence but does not claim a measured residential percentage or verified access for every site. Private, restricted or obsolete sites may still be present in the third-party listings and need review before operational use.

## Ten-minute target

The intention remains **at most ten minutes driving between consecutive local collection stops**, excluding collection time. Expanding the region does not mean every point is within ten minutes of Heilbronn or of every other point. A road-routing engine must validate selected legs and split routes where necessary. The SQL does not invent driving times or promise this constraint; the current application's straight-line route preview cannot enforce it.

## Proposed SQLite SQL

This is concrete SQL with all 449 coordinate rows embedded. The approved source-database update has already been applied, as recorded above. For future review, run this complete preview script in one connection **against a separate demo copy**, stopping on the first error. It demonstrates the coordinate update inside a transaction and finishes with `ROLLBACK` so this preview saves no changes. It does not add, delete or merge UUIDs or modify `raw_data`.

```sql
BEGIN;

CREATE TEMP TABLE coordinate_sources (
    source_id INTEGER PRIMARY KEY,
    source_kind TEXT NOT NULL CHECK (
        source_kind IN ('official_heilbronn', 'regional_glass_map')
    ),
    source_url TEXT NOT NULL
);

INSERT INTO coordinate_sources VALUES
    (1, 'official_heilbronn', 'https://karten.heilbronn.de/heilbronn/index.php?service=heilbronn&layers=altglascontainerstandorte'),
    (2, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/abstatt'),
    (3, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/aspach'),
    (4, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/backnang'),
    (5, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/bad-friedrichshall'),
    (6, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/bad-rappenau'),
    (7, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/bad-wimpfen'),
    (8, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/beilstein'),
    (9, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/brackenheim'),
    (10, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/burgstetten'),
    (11, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/eberstadt'),
    (12, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/ellhofen'),
    (13, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/elztal'),
    (14, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/eppingen'),
    (15, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/flein'),
    (16, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/forchtenberg'),
    (17, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/freiberg-am-neckar'),
    (18, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/grosserlach'),
    (19, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/gueglingen'),
    (20, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/gundelsheim'),
    (21, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/hueffenhardt'),
    (22, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/ilsfeld'),
    (23, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/kirchardt'),
    (24, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/kirchberg-an-der-murr'),
    (25, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/kirchheim-am-neckar'),
    (26, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/kuernbach'),
    (27, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/lauffen-am-neckar'),
    (28, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/lehrensteinsfeld'),
    (29, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/leingarten'),
    (30, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/leutenbach'),
    (31, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/loewenstein'),
    (32, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/ludwigsburg'),
    (33, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/moeckmuehl'),
    (34, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/mosbach'),
    (35, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/neckarsulm'),
    (36, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/neckarwestheim'),
    (37, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/neuenstadt-am-kocher'),
    (38, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/neuenstein'),
    (39, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/nordheim'),
    (40, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/obersulm'),
    (41, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/oehringen'),
    (42, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/offenau'),
    (43, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/oppenweiler'),
    (44, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/remseck-am-neckar'),
    (45, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/schwaigern'),
    (46, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/spiegelberg'),
    (47, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/sulzbach-an-der-murr'),
    (48, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/talheim'),
    (49, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/untereisesheim'),
    (50, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/untergruppenbach'),
    (51, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/waiblingen'),
    (52, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/weinsberg'),
    (53, 'regional_glass_map', 'https://containerstandorte.de/glascontainer/wuestenrot');

CREATE TEMP TABLE proposed_points (
    point_id INTEGER PRIMARY KEY,
    latitude REAL NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude REAL NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    municipality TEXT NOT NULL,
    source_id INTEGER NOT NULL,
    source_reference TEXT NOT NULL,
    distance_from_heilbronn_metres REAL NOT NULL CHECK (
        distance_from_heilbronn_metres BETWEEN 0 AND 28600
    ),
    UNIQUE (latitude, longitude)
);

-- WGS84 latitude then longitude. UUID-to-coordinate assignments are synthetic.
INSERT INTO proposed_points VALUES
    (1, 49.13908296, 9.21781326, 'Heilbronn', 1, 'utm:515887,5442940', 189.810),
    (2, 49.14337412, 9.21762640, 'Heilbronn', 1, 'utm:515872,5443417', 325.858),
    (3, 49.14025681, 9.22487931, 'Heilbronn', 1, 'utm:516402,5443072', 426.897),
    (4, 49.13936281, 9.21245379, 'Heilbronn', 1, 'utm:515496,5442970', 497.755),
    (5, 49.13651892, 9.22271002, 'Heilbronn', 1, 'utm:516245,5442656', 525.979),
    (6, 49.14588996, 9.21914574, 'Heilbronn', 1, 'utm:515982,5443697', 589.176),
    (7, 49.14426867, 9.22492489, 'Heilbronn', 1, 'utm:516404,5443518', 592.300),
    (8, 49.14116812, 9.22805062, 'Heilbronn', 1, 'utm:516633,5443174', 659.079),
    (9, 49.14147303, 9.20955611, 'Heilbronn', 1, 'utm:515284,5443204', 696.330),
    (10, 49.13373197, 9.21713180, 'Heilbronn', 1, 'utm:515839,5442345', 775.228),
    (11, 49.13355522, 9.22021547, 'Heilbronn', 1, 'utm:516064,5442326', 787.154),
    (12, 49.13986561, 9.20802748, 'Heilbronn', 1, 'utm:515173,5443025', 804.676),
    (13, 49.13875236, 9.23056219, 'Heilbronn', 1, 'utm:516817,5442906', 863.262),
    (14, 49.14385298, 9.23044873, 'Heilbronn', 1, 'utm:516807,5443473', 906.106),
    (15, 49.14831899, 9.22369536, 'Heilbronn', 1, 'utm:516313,5443968', 923.715),
    (16, 49.13686218, 9.20745282, 'Heilbronn', 1, 'utm:515132,5442691', 938.992),
    (17, 49.13388698, 9.21115547, 'Heilbronn', 1, 'utm:515403,5442361', 940.368),
    (18, 49.13227907, 9.22426748, 'Heilbronn', 1, 'utm:516360,5442185', 999.706),
    (19, 49.14984023, 9.22316740, 'Heilbronn', 1, 'utm:516274,5444137', 1071.433),
    (20, 49.14122809, 9.23404249, 'Heilbronn', 1, 'utm:517070,5443182', 1094.118),
    (21, 49.13109328, 9.22343965, 'Heilbronn', 1, 'utm:516300,5442053', 1103.774),
    (22, 49.14013019, 9.23427040, 'Heilbronn', 1, 'utm:517087,5443060', 1109.608),
    (23, 49.15125857, 9.22000595, 'Heilbronn', 1, 'utm:516043,5444294', 1188.190),
    (24, 49.13163027, 9.22941880, 'Heilbronn', 1, 'utm:516736,5442114', 1250.540),
    (25, 49.13215730, 9.20761140, 'Heilbronn', 1, 'utm:515145,5442168', 1253.035),
    (26, 49.15081426, 9.22649042, 'Heilbronn', 1, 'utm:516516,5444246', 1259.461),
    (27, 49.13382616, 9.23340446, 'Heilbronn', 1, 'utm:517026,5442359', 1288.035),
    (28, 49.14463254, 9.23640323, 'Heilbronn', 1, 'utm:517241,5443561', 1341.022),
    (29, 49.15067102, 9.23068606, 'Heilbronn', 1, 'utm:516822,5444231', 1405.163),
    (30, 49.12841017, 9.21039202, 'Heilbronn', 1, 'utm:515349,5441752', 1493.328),
    (31, 49.12719291, 9.22154428, 'Heilbronn', 1, 'utm:516163,5441619', 1501.055),
    (32, 49.15370678, 9.22392534, 'Heilbronn', 1, 'utm:516328,5444567', 1501.093),
    (33, 49.15303337, 9.22788565, 'Heilbronn', 1, 'utm:516617,5444493', 1525.930),
    (34, 49.15392424, 9.21359948, 'Heilbronn', 1, 'utm:515575,5444589', 1534.269),
    (35, 49.13316238, 9.23689702, 'Heilbronn', 1, 'utm:517281,5442286', 1539.934),
    (36, 49.13975784, 9.24036975, 'Heilbronn', 1, 'utm:517532,5443020', 1554.889),
    (37, 49.12879439, 9.20684345, 'Heilbronn', 1, 'utm:515090,5441794', 1583.467),
    (38, 49.15335828, 9.23186423, 'Heilbronn', 1, 'utm:516907,5444530', 1698.859),
    (39, 49.14848594, 9.23913669, 'Heilbronn', 1, 'utm:517439,5443990', 1705.520),
    (40, 49.12540034, 9.21331246, 'Heilbronn', 1, 'utm:515563,5441418', 1739.745),
    (41, 49.15534571, 9.22762197, 'Heilbronn', 1, 'utm:516597,5444750', 1755.460),
    (42, 49.12548263, 9.22677251, 'Heilbronn', 1, 'utm:516545,5441430', 1771.918),
    (43, 49.12558945, 9.20826930, 'Heilbronn', 1, 'utm:515195,5441438', 1842.871),
    (44, 49.14112308, 9.19359535, 'Heilbronn', 1, 'utm:514120,5443162', 1851.396),
    (45, 49.13795656, 9.19367898, 'Heilbronn', 1, 'utm:514127,5442810', 1867.561),
    (46, 49.12408420, 9.22428534, 'Heilbronn', 1, 'utm:516364,5441274', 1874.923),
    (47, 49.14633028, 9.19427382, 'Heilbronn', 1, 'utm:514168,5443741', 1910.697),
    (48, 49.12400162, 9.22968514, 'Heilbronn', 1, 'utm:516758,5441266', 2000.931),
    (49, 49.14397747, 9.19189253, 'Heilbronn', 1, 'utm:513995,5443479', 2009.838),
    (50, 49.13312865, 9.24445026, 'Heilbronn', 1, 'utm:517832,5442284', 2026.768),
    (51, 49.13852947, 9.24699946, 'Heilbronn', 1, 'utm:518016,5442885', 2047.309),
    (52, 49.14006622, 9.19083544, 'Heilbronn', 1, 'utm:513919,5443044', 2052.075),
    (53, 49.12603375, 9.20121228, 'Heilbronn', 1, 'utm:514680,5441486', 2074.022),
    (54, 49.13690090, 9.19019264, 'Heilbronn', 1, 'utm:513873,5442692', 2137.834),
    (55, 49.14547170, 9.24803494, 'Heilbronn', 1, 'utm:518089,5443657', 2178.267),
    (56, 49.15634902, 9.20077273, 'Heilbronn', 1, 'utm:514639,5444856', 2198.603),
    (57, 49.13403641, 9.24901975, 'Heilbronn', 1, 'utm:518165,5442386', 2300.053),
    (58, 49.13172819, 9.19040589, 'Heilbronn', 1, 'utm:513890,5442117', 2304.103),
    (59, 49.14717563, 9.18898414, 'Heilbronn', 1, 'utm:513782,5443834', 2305.098),
    (60, 49.12098412, 9.20808555, 'Heilbronn', 1, 'utm:515183,5440926', 2321.231),
    (61, 49.12177228, 9.20497772, 'Heilbronn', 1, 'utm:514956,5441013', 2329.158),
    (62, 49.12003293, 9.21175449, 'Heilbronn', 1, 'utm:515451,5440821', 2346.594),
    (63, 49.15528722, 9.19573517, 'Heilbronn', 1, 'utm:514272,5444737', 2354.064),
    (64, 49.12313005, 9.20015889, 'Heilbronn', 1, 'utm:514604,5441163', 2378.207),
    (65, 49.14489483, 9.18650735, 'Heilbronn', 1, 'utm:513602,5443580', 2413.867),
    (66, 49.16222605, 9.22818844, 'Heilbronn', 1, 'utm:516636,5445515', 2496.058),
    (67, 49.11836920, 9.20655342, 'Heilbronn', 1, 'utm:515072,5440635', 2632.608),
    (68, 49.15900145, 9.19624357, 'Heilbronn', 1, 'utm:514308,5445150', 2633.963),
    (69, 49.12882777, 9.18728322, 'Heilbronn', 1, 'utm:513663,5441794', 2654.586),
    (70, 49.12189621, 9.19576819, 'Heilbronn', 1, 'utm:514284,5441025', 2680.854),
    (71, 49.15077046, 9.18548718, 'Heilbronn', 1, 'utm:513526,5444233', 2689.751),
    (72, 49.14455973, 9.18229661, 'Heilbronn', 1, 'utm:513295,5443542', 2708.453),
    (73, 49.11909934, 9.20059492, 'Heilbronn', 1, 'utm:514637,5440715', 2740.668),
    (74, 49.15388052, 9.18693879, 'Heilbronn', 1, 'utm:513631,5444579', 2762.735),
    (75, 49.14752860, 9.18204696, 'Heilbronn', 1, 'utm:513276,5443872', 2798.741),
    (76, 49.11669584, 9.20666980, 'Heilbronn', 1, 'utm:515081,5440449', 2805.269),
    (77, 49.13609581, 9.25747502, 'Heilbronn', 1, 'utm:518781,5442617', 2840.881),
    (78, 49.14205355, 9.18003881, 'Heilbronn', 1, 'utm:513131,5443263', 2841.235),
    (79, 49.16376087, 9.20096730, 'Heilbronn', 1, 'utm:514651,5445680', 2891.970),
    (80, 49.13884339, 9.17927313, 'Heilbronn', 1, 'utm:513076,5442906', 2898.901),
    (81, 49.14887110, 9.18065317, 'Heilbronn', 1, 'utm:513174,5444021', 2939.576),
    (82, 49.11811613, 9.19694559, 'Heilbronn', 1, 'utm:514371,5440605', 2971.325),
    (83, 49.11936354, 9.19337360, 'Heilbronn', 1, 'utm:514110,5440743', 3009.577),
    (84, 49.16614797, 9.20420060, 'Heilbronn', 1, 'utm:514886,5445946', 3039.559),
    (85, 49.14585312, 9.17777638, 'Heilbronn', 1, 'utm:512965,5443685', 3057.534),
    (86, 49.13998985, 9.17664486, 'Heilbronn', 1, 'utm:512884,5443033', 3084.259),
    (87, 49.11773323, 9.18922857, 'Heilbronn', 1, 'utm:513808,5440561', 3341.181),
    (88, 49.16763519, 9.19730654, 'Heilbronn', 1, 'utm:514383,5446110', 3396.929),
    (89, 49.13739045, 9.17047997, 'Heilbronn', 1, 'utm:512435,5442743', 3549.982),
    (90, 49.15536463, 9.17556121, 'Heilbronn', 1, 'utm:512801,5444742', 3563.110),
    (91, 49.11699486, 9.18412784, 'Heilbronn', 1, 'utm:513436,5440478', 3651.731),
    (92, 49.17107022, 9.19800614, 'Heilbronn', 1, 'utm:514433,5446492', 3718.039),
    (93, 49.11844932, 9.18020004, 'Heilbronn', 1, 'utm:513149,5440639', 3747.763),
    (94, 49.15765100, 9.17454065, 'Heilbronn', 1, 'utm:512726,5444996', 3751.007),
    (95, 49.16802748, 9.18863822, 'Heilbronn', 1, 'utm:513751,5446152', 3767.343),
    (96, 49.17429505, 9.20061206, 'Heilbronn', 1, 'utm:514622,5446851', 3979.843),
    (97, 49.15367961, 9.27607968, 'Weinsberg', 52, '6e2c61e1-c6b6-4b36-9a15-3b0855f84ecf', 4397.064),
    (98, 49.10293116, 9.19924274, 'Flein', 15, '70c9be85-b803-4420-b47f-48a5c0e379b7', 4428.412),
    (99, 49.10236070, 9.19998490, 'Flein', 15, '51283bfd-55eb-4664-86c3-46b9dcef427c', 4471.409),
    (100, 49.11413457, 9.17230502, 'Heilbronn', 1, 'utm:512574,5440158', 4496.187),
    (101, 49.10100180, 9.20154940, 'Flein', 15, '11ae892e-72cc-4d03-b186-fc30e65b9af9', 4582.402),
    (102, 49.16427446, 9.16651198, 'Heilbronn', 1, 'utm:512139,5445731', 4639.493),
    (103, 49.11339331, 9.16867114, 'Heilbronn', 1, 'utm:512309,5440075', 4751.385),
    (104, 49.18316170, 9.22945290, 'Neckarsulm', 35, 'a2c15190-2f48-462b-9627-84f5117b24aa', 4793.798),
    (105, 49.18424410, 9.22317190, 'Neckarsulm', 35, '88a3dc3a-b387-49fd-9f79-989feaf11f1f', 4863.225),
    (106, 49.14458170, 9.28606090, 'Weinsberg', 52, 'a61076f4-bf1d-49cc-b224-870703215ee0', 4895.824),
    (107, 49.09471440, 9.21636120, 'Flein', 15, 'ee24a25c-bffb-405c-8ba1-9a4677e79154', 5105.048),
    (108, 49.10646000, 9.26664910, 'Untergruppenbach', 50, '64ace49e-6df3-41e5-b896-97ed612339f2', 5139.093),
    (109, 49.18695368, 9.22306164, 'Neckarsulm', 35, '800ffb6f-5195-44eb-a8fa-d8af44640906', 5163.511),
    (110, 49.18664120, 9.22909510, 'Neckarsulm', 35, '4d876409-9037-45dd-b96f-b99e6a29ef25', 5172.452),
    (111, 49.18627960, 9.23313000, 'Neckarsulm', 35, 'c6d0a231-5201-46a3-a476-42b021cd4455', 5182.611),
    (112, 49.10261040, 9.26281500, 'Untergruppenbach', 50, '9d588bcd-1af8-4bb0-8cb2-77d9ff263ba3', 5290.354),
    (113, 49.11716544, 9.15360940, 'Heilbronn', 1, 'utm:511209,5440492', 5426.447),
    (114, 49.15439540, 9.29207600, 'Weinsberg', 52, 'd34f3efe-457c-4b67-845f-81f752fb275a', 5529.979),
    (115, 49.18349449, 9.18050472, 'Heilbronn', 1, 'utm:513154,5447870', 5532.330),
    (116, 49.18802300, 9.24769410, 'Neckarsulm', 35, 'c1404a28-503f-4427-ad2e-d196f1e24641', 5670.875),
    (117, 49.19265990, 9.22853160, 'Neckarsulm', 35, 'dc6e51bb-2158-4656-a8a2-88e747973402', 5830.740),
    (118, 49.19201928, 9.20297414, 'Neckarsulm', 35, '5f961efe-7901-4134-b6c8-b31524c04214', 5836.450),
    (119, 49.08511170, 9.20108080, 'Talheim', 48, 'ecd62abd-939a-411e-83cc-f0ca9fd42495', 6305.978),
    (120, 49.19536490, 9.19618920, 'Neckarsulm', 35, 'b1c138c3-1f7a-4113-b67b-8e627098a7fb', 6312.877),
    (121, 49.16618690, 9.29745410, 'Weinsberg', 52, '68e4b11d-44bc-4601-add4-ae0dd9506e89', 6373.881),
    (122, 49.09451980, 9.27116040, 'Untergruppenbach', 50, 'd08c1e88-754a-40e8-85a3-33696881089d', 6374.732),
    (123, 49.10536220, 9.28822610, 'Untergruppenbach', 50, '15162692-8f02-484f-87b6-22fe40e1d966', 6379.552),
    (124, 49.08594010, 9.19183080, 'Talheim', 48, '8f9625d2-a66a-4e5a-82a7-5132a895d532', 6391.400),
    (125, 49.14795360, 9.13118080, 'Leingarten', 29, 'a9d308a3-2424-4b46-8561-433160ba046e', 6442.507),
    (126, 49.09346480, 9.27458220, 'Untergruppenbach', 50, 'd977b13d-5600-48ff-bb22-8e0cb966b510', 6618.520),
    (127, 49.19989150, 9.22844350, 'Neckarsulm', 35, '55ef4f0d-f232-4686-9624-0141d20914d3', 6629.212),
    (128, 49.19993700, 9.23074280, 'Neckarsulm', 35, '8a1d643b-a299-4a91-ab5f-11c453902c8e', 6653.560),
    (129, 49.10810060, 9.14125720, 'Nordheim', 39, '964a37fb-b95a-404e-9996-4ab80851e862', 6714.468),
    (130, 49.14562460, 9.12686040, 'Leingarten', 29, 'eae65c0a-1480-4592-8868-4900cde45df8', 6728.023),
    (131, 49.19944370, 9.24395060, 'Neckarsulm', 35, '83f4170b-5b53-45f0-87bf-d7248f49738d', 6790.128),
    (132, 49.09294350, 9.27778540, 'Untergruppenbach', 50, '6ad47cad-f572-40ca-a9a5-3f6fd789d7eb', 6808.463),
    (133, 49.08923540, 9.27256540, 'Untergruppenbach', 50, '9385b20a-008b-41ef-919b-e69ca235b1d6', 6913.096),
    (134, 49.15387389, 9.31290229, 'Ellhofen', 12, '0c4a3c61-5d50-4939-aa5f-ede453f1b04d', 6985.431),
    (135, 49.18327780, 9.28952150, 'Weinsberg', 52, '35dbde88-2e48-4fe1-a0aa-f8daad5c0f90', 6985.604),
    (136, 49.07841110, 9.19107350, 'Talheim', 48, 'e1bd829d-e254-40ac-baec-a8b7502bf0ba', 7207.495),
    (137, 49.10462740, 9.13520560, 'Nordheim', 39, 'd25b91ac-66b2-4d32-94eb-cfe9470af656', 7294.171),
    (138, 49.11076220, 9.12908100, 'Nordheim', 39, '97736b07-7e9e-4acf-a789-54ce1fa25f46', 7337.930),
    (139, 49.20626500, 9.20178930, 'Untereisesheim', 49, 'fa0a4707-178e-49b6-b381-62bf16f16c4a', 7409.332),
    (140, 49.13504660, 9.11721100, 'Leingarten', 29, '21a5830b-e02c-4cbd-bcff-55bfe07977cb', 7433.022),
    (141, 49.14755436, 9.32168578, 'Ellhofen', 12, 'd2f546a3-ef63-48ff-803c-fa2e083b4a2d', 7506.888),
    (142, 49.14467100, 9.32444750, 'Ellhofen', 12, 'f10f8abd-3d3d-4f26-9e1d-950c6b7a1988', 7681.371),
    (143, 49.21015019, 9.22642616, 'Bad Friedrichshall', 5, '83d2b644-ddbb-4ba7-a43b-3a050c35492c', 7753.179),
    (144, 49.14344990, 9.11225890, 'Leingarten', 29, 'df520cb8-eb86-4036-839f-c176f558ef12', 7773.500),
    (145, 49.13204250, 9.32562550, 'Lehrensteinsfeld', 28, '4fddf736-47f4-4602-8069-79ad36ad9f01', 7812.698),
    (146, 49.19050049, 9.14292545, 'Heilbronn', 1, 'utm:510414,5448643', 7837.017),
    (147, 49.10211900, 9.12820570, 'Nordheim', 39, '8c7c9652-82d7-428b-a54c-4a6e9dec62d1', 7873.372),
    (148, 49.08724811, 9.29033154, 'Untergruppenbach', 50, '828653d4-da19-471b-93cb-ecbc7b1aba64', 7881.150),
    (149, 49.21192160, 9.21615220, 'Bad Friedrichshall', 5, '4c5b6c76-03e3-4edd-9e21-cfe3783798c8', 7934.267),
    (150, 49.12802410, 9.32745780, 'Lehrensteinsfeld', 28, '1ef06beb-b2d9-4e53-8887-e63f90716f75', 8011.097),
    (151, 49.12482640, 9.32660690, 'Lehrensteinsfeld', 28, '9aff9c85-3823-4c44-9d13-08d9e4d33495', 8020.537),
    (152, 49.10560230, 9.12215630, 'Nordheim', 39, 'c14b7740-6e8c-4d1f-9f2a-930ce9380b50', 8052.080),
    (153, 49.18095759, 9.12652796, 'Heilbronn', 1, 'utm:509221,5447580', 8086.531),
    (154, 49.06738497, 9.21663600, 'Ilsfeld', 22, '01d95414-41b4-4ef7-a348-e3c1915d6584', 8142.108),
    (155, 49.07495960, 9.16881850, 'Lauffen am Neckar', 27, 'a58ed7a5-ca82-435e-a285-f8948b55c330', 8162.190),
    (156, 49.21196810, 9.24662890, 'Neckarsulm', 35, '28a6d687-a835-4d2c-9fbf-5b5ed0968e0e', 8186.253),
    (157, 49.07619400, 9.16328460, 'Lauffen am Neckar', 27, '93df8342-327f-40ad-ae99-594e380ef1fa', 8230.643),
    (158, 49.08511420, 9.29497400, 'Abstatt', 2, '2e93ab4c-6c89-4c62-af03-930c7727591c', 8282.879),
    (159, 49.19892326, 9.14757562, 'Heilbronn', 1, 'utm:510751,5449580', 8310.174),
    (160, 49.21421040, 9.19872220, 'Untereisesheim', 49, 'bc93d413-e911-4665-b723-bb549a9df6f1', 8318.082),
    (161, 49.21485860, 9.20071360, 'Untereisesheim', 49, '8041533c-8663-4bf6-842b-ac9a9cb1db66', 8364.761),
    (162, 49.14581752, 9.10424636, 'Leingarten', 29, 'f01397f2-a9fc-4b4e-a1cd-e671e3a38a4b', 8369.845),
    (163, 49.07299640, 9.27203214, 'Ilsfeld', 22, '49aafd02-b6f5-46a2-9e76-d5f3ee9f51aa', 8448.580),
    (164, 49.18237570, 9.31767870, 'Eberstadt', 11, '0f0f0f88-98df-49a0-bd52-092a4920207e', 8546.151),
    (165, 49.19628241, 9.13721839, 'Heilbronn', 1, 'utm:509997,5449285', 8586.526),
    (166, 49.07650080, 9.15100160, 'Lauffen am Neckar', 27, '6e8cb082-b2c3-48bc-8c76-de0eca416e78', 8678.243),
    (167, 49.07702370, 9.14922550, 'Lauffen am Neckar', 27, '475244a7-9644-4d49-9400-20725b51aba8', 8705.369),
    (168, 49.07866200, 9.29329510, 'Abstatt', 2, '50375764-4f2f-47c7-8fc2-b55be71e57ea', 8754.449),
    (169, 49.18184992, 9.11626620, 'Heilbronn', 1, 'utm:508473,5447678', 8768.504),
    (170, 49.18452822, 9.11853672, 'Heilbronn', 1, 'utm:508638,5447976', 8790.042),
    (171, 49.14562890, 9.34166040, 'Obersulm', 40, 'cec52528-4d8d-4393-b33a-bb10d663aa7d', 8937.537),
    (172, 49.10545510, 9.10622830, 'Nordheim', 39, 'e27f6f8d-bc1f-44e1-a9e4-fee672a801aa', 9091.188),
    (173, 49.07284430, 9.14896980, 'Lauffen am Neckar', 27, 'f483ba36-5a5d-41ef-8623-044d90e6c913', 9097.304),
    (174, 49.07118030, 9.15281390, 'Lauffen am Neckar', 27, '41d02175-35a3-4ecc-a7cc-2800b1a74dd6', 9099.868),
    (175, 49.09522850, 9.32428940, 'Untergruppenbach', 50, '7e3966bd-143c-40d6-b64e-6c71505a385b', 9171.897),
    (176, 49.20717650, 9.29397840, 'Neckarsulm', 35, '8733fffc-6ffd-4239-964d-904f6ed74ed6', 9192.379),
    (177, 49.18218318, 9.10648315, 'Heilbronn', 1, 'utm:507760,5447714', 9400.273),
    (178, 49.07393700, 9.13954610, 'Lauffen am Neckar', 27, '20a41344-0929-447c-8f1e-b898a283549c', 9402.781),
    (179, 49.09050040, 9.32343130, 'Untergruppenbach', 50, 'ae7e713f-f382-42a2-a1fd-4cbaaff0caa6', 9421.071),
    (180, 49.06705760, 9.28473510, 'Abstatt', 2, '1062c235-d5e2-40cd-a258-f523a3808e37', 9472.818),
    (181, 49.08507870, 9.31833400, 'Untergruppenbach', 50, '6353f8da-3647-49b4-b2ef-9571a3e81bf7', 9504.816),
    (182, 49.10191770, 9.10233680, 'Nordheim', 39, 'ce02db97-247f-4eed-ac99-622fbb06c1a6', 9519.063),
    (183, 49.07071310, 9.14291650, 'Lauffen am Neckar', 27, '4ae0637a-69ef-4760-94dd-9918909aa1f5', 9543.465),
    (184, 49.18604221, 9.10645026, 'Heilbronn', 1, 'utm:507757,5448143', 9620.404),
    (185, 49.18953018, 9.33009340, 'Eberstadt', 11, '3d903f49-62ba-44c4-9082-0e2512519e3b', 9737.434),
    (186, 49.06944370, 9.13995560, 'Lauffen am Neckar', 27, '5fe778c5-fecb-4ce2-b5a3-975c45bcd508', 9784.022),
    (187, 49.06639380, 9.14564240, 'Lauffen am Neckar', 27, '96df9ec2-93e0-4792-b746-f3182549aa4d', 9829.293),
    (188, 49.06090490, 9.27890590, 'Ilsfeld', 22, 'c65bd407-39aa-4bbe-8145-03f2b43f456d', 9874.892),
    (189, 49.05256936, 9.24633816, 'Ilsfeld', 22, '88f868e9-57ec-4676-b867-2edf912d0c75', 9987.519),
    (190, 49.22977820, 9.19794570, 'Bad Friedrichshall', 5, '1bfd46f0-7216-47a1-9e0e-addbd85e1d03', 10034.796),
    (191, 49.23120940, 9.21247790, 'Bad Friedrichshall', 5, '4c005def-145d-4f81-b4ea-de5a6cb99394', 10087.466),
    (192, 49.22366140, 9.16237826, 'Bad Wimpfen', 7, '00264b25-7eec-4a08-a2ec-cccfed5e5a39', 10113.227),
    (193, 49.05128620, 9.24747560, 'Ilsfeld', 22, 'bc71e5ba-c3a3-460f-8649-23ec68a61e42', 10143.972),
    (194, 49.17983610, 9.34570950, 'Eberstadt', 11, 'e0d65eaf-c306-4c4f-a3c1-c3f776d386fa', 10192.686),
    (195, 49.06556130, 9.13814910, 'Lauffen am Neckar', 27, '67d12e2f-92aa-45cf-8882-a7a66bbaaedc', 10211.670),
    (196, 49.04981550, 9.19197810, 'Neckarwestheim', 36, 'f1977eb4-73d7-408e-85be-e7b1a1420ac1', 10284.299),
    (197, 49.22534220, 9.16219260, 'Bad Wimpfen', 7, '9537e2a6-bd95-4775-8d85-6da8b8f7c5cd', 10289.592),
    (198, 49.13418990, 9.36036414, 'Obersulm', 40, 'a7b24c54-dfcd-4e20-9dfc-85ee3ac58a3a', 10306.292),
    (199, 49.23021454, 9.18232962, 'Bad Wimpfen', 7, 'f68bf2bb-a879-4c8a-9cd4-5d4392256979', 10316.433),
    (200, 49.06542940, 9.13500240, 'Lauffen am Neckar', 27, '0dc20519-da04-44ad-b1e1-9ae5d0e9ddaa', 10357.291),
    (201, 49.13952710, 9.36147190, 'Obersulm', 40, '43011527-35de-47e5-a1f7-4cf1b56a5fc7', 10362.384),
    (202, 49.22296830, 9.15212380, 'Bad Wimpfen', 7, 'f507f671-6684-40e5-a7c2-ce478a400def', 10370.810),
    (203, 49.06320220, 9.13907920, 'Lauffen am Neckar', 27, '92105f93-a3ac-4e5d-91a7-bc355d8a2996', 10389.075),
    (204, 49.22631190, 9.16022270, 'Bad Wimpfen', 7, 'ceacf4dc-86c7-4402-a4db-5722ff7626f5', 10446.183),
    (205, 49.23454690, 9.22170840, 'Bad Friedrichshall', 5, '4f726c8d-4645-484a-a6a7-c2c54f7b09b3', 10449.130),
    (206, 49.05626750, 9.28260720, 'Ilsfeld', 22, '1aece7e1-32e0-4de3-b41a-7630cc7e7c42', 10456.642),
    (207, 49.13412830, 9.36729600, 'Obersulm', 40, 'b0d4d608-be34-44bc-acb7-ab321efb4ee6', 10809.889),
    (208, 49.23777240, 9.20152000, 'Bad Friedrichshall', 5, 'd2533f17-0fd5-43f6-a1a8-b963896bff24', 10880.675),
    (209, 49.04332650, 9.19737260, 'Neckarwestheim', 36, '3282faa5-98a1-4ebc-a19e-3511fbca2217', 10929.817),
    (210, 49.13340110, 9.36920130, 'Obersulm', 40, '30afc5ca-6d5b-4da8-b9f7-c6be19cbbd26', 10953.880),
    (211, 49.04267713, 9.20051622, 'Neckarwestheim', 36, '12cd203f-bac9-449f-ae41-c5df2f0dda77', 10970.796),
    (212, 49.22919350, 9.15149840, 'Bad Wimpfen', 7, 'caa2148c-0940-488f-8fb5-cd00464af12e', 11007.048),
    (213, 49.13675812, 9.06672063, 'Schwaigern', 45, '76ebfaab-c384-4313-a31c-14dac7b087a5', 11088.499),
    (214, 49.07976490, 9.09822860, 'Brackenheim', 9, 'e176f762-b784-4f0b-9bd8-7635b8104a1a', 11093.603),
    (215, 49.23073177, 9.15023078, 'Bad Wimpfen', 7, 'f5a39744-a655-426a-9356-1dd9bdd380dc', 11201.197),
    (216, 49.05960300, 9.31069140, 'Ilsfeld', 22, 'c41d94ae-7210-4682-8e67-c5df14b337ed', 11208.460),
    (217, 49.04180760, 9.18784650, 'Neckarwestheim', 36, 'c2bc4f7d-a86f-43eb-b9e1-684765a00138', 11216.602),
    (218, 49.08925690, 9.35550620, 'Untergruppenbach', 50, '6d628277-2f85-4130-a01d-32a718ff04de', 11456.145),
    (219, 49.13894120, 9.06146280, 'Schwaigern', 45, '8f846feb-cd2f-4b7e-b91a-69a4ff1d54e3', 11464.010),
    (220, 49.13282970, 9.37627020, 'Obersulm', 40, '2a751dcc-a0ac-490c-8049-6d93779b4329', 11471.500),
    (221, 49.14243620, 9.06073490, 'Schwaigern', 45, 'cff81b64-ab82-4f0c-8e77-6f964953446f', 11516.912),
    (222, 49.16563670, 9.06513072, 'Schwaigern', 45, '79d8db7b-019a-4321-9f81-f895e9f149ad', 11533.949),
    (223, 49.08767860, 9.07874710, 'Brackenheim', 9, 'cc15cf5d-8e78-4f8d-9bc5-d623961157f8', 11784.367),
    (224, 49.13894550, 9.38123130, 'Obersulm', 40, '6d4423bb-d1bc-44fa-b6bf-3d30ecb8b3c7', 11800.596),
    (225, 49.14912840, 9.05662840, 'Schwaigern', 45, 'eeb93d27-1bd7-4c5a-8480-41709642db4d', 11851.083),
    (226, 49.24082170, 9.16229340, 'Offenau', 42, 'db9dceb1-aab3-4a88-8172-36a96334ec30', 11883.345),
    (227, 49.12192920, 9.38079480, 'Obersulm', 40, '1431bb46-5efa-46fe-9d32-f2e00696b51b', 11950.991),
    (228, 49.24236070, 9.16467940, 'Offenau', 42, 'd1b872a9-7dce-4f1a-8c59-4a9be28f192f', 11985.713),
    (229, 49.12063810, 9.38102100, 'Löwenstein', 31, '76b01c27-3902-452c-8cc3-9c3aa0515100', 11993.079),
    (230, 49.24319930, 9.16573230, 'Offenau', 42, 'a5c10eb3-ed80-4c58-bef9-f59febffd1b1', 12048.967),
    (231, 49.12273530, 9.38255370, 'Obersulm', 40, '63c28d71-e90e-40d8-a9f7-dc203ccc48b0', 12061.868),
    (232, 49.11982410, 9.38236030, 'Obersulm', 40, '56000cff-45c4-40fc-abd6-3e0636bb995b', 12105.891),
    (233, 49.08833250, 9.07288410, 'Brackenheim', 9, 'bd618661-6c72-4484-a6ea-4675c2111943', 12120.881),
    (234, 49.21207868, 9.09308418, 'Bad Rappenau', 6, '53b4caca-11ff-4143-9cd2-8ace13976d7b', 12124.711),
    (235, 49.24617690, 9.17610730, 'Offenau', 42, 'f0c23ce9-946f-4704-81ab-0722307110cc', 12147.829),
    (236, 49.11936460, 9.38314910, 'Löwenstein', 31, '655e1038-8dba-4cfa-a4ef-2ab01d6a07bf', 12172.094),
    (237, 49.24926030, 9.19481660, 'Bad Friedrichshall', 5, '0d3934ba-1630-4d9c-a67a-befc21d1c1fb', 12210.836),
    (238, 49.11775110, 9.38352168, 'Löwenstein', 31, '59c04f00-0c1a-4f3a-9cae-7a03ab4721cf', 12234.861),
    (239, 49.11715524, 9.38473236, 'Löwenstein', 31, 'd0f6ee9e-7aa2-49b9-bf80-edf6b3a0823e', 12334.945),
    (240, 49.13888160, 9.04891130, 'Schwaigern', 45, '5494d649-9947-409f-9187-0698f31906a4', 12377.074),
    (241, 49.06843590, 9.08932670, 'Brackenheim', 9, 'f5a2c7be-da08-433c-96cb-6981653a0108', 12390.769),
    (242, 49.07856840, 9.07746020, 'Brackenheim', 9, 'ca2b4eb8-020f-4d5f-a5b2-df80bf43f2f7', 12399.956),
    (243, 49.04516890, 9.30788130, 'Beilstein', 8, 'e76e516a-80df-4b99-ab6b-80f8b18b3af1', 12427.268),
    (244, 49.14545490, 9.04823190, 'Schwaigern', 45, '90234218-d89d-4b0a-bd6c-e80d1e7e030d', 12435.974),
    (245, 49.21469934, 9.08774506, 'Bad Rappenau', 6, '2e6bdbb9-aecc-4765-82cb-a29d1b531ba5', 12608.677),
    (246, 49.06855890, 9.08368010, 'Brackenheim', 9, '48606b5c-91b6-48c9-83df-8d091ccfa294', 12698.158),
    (247, 49.08455020, 9.06659650, 'Brackenheim', 9, '317a0794-5bef-45e6-acfe-513470be6ac5', 12725.368),
    (248, 49.23283980, 9.11436420, 'Bad Wimpfen', 7, 'f22010f9-7ab8-42e9-988a-bf113f2d3e8b', 12770.377),
    (249, 49.06347990, 9.08758370, 'Brackenheim', 9, '70584be1-400e-4209-9b3b-aa601dda6964', 12849.099),
    (250, 49.03420080, 9.14860790, 'Kirchheim am Neckar', 25, 'fd0a11cd-6834-4e81-809d-b67f2d97919c', 12893.963),
    (251, 49.10519310, 9.04983890, 'Brackenheim', 9, '318247ec-815c-4ba7-a855-31bc8acbcf2e', 12926.195),
    (252, 49.24308000, 9.30359770, 'Neuenstadt am Kocher', 37, 'cf358787-34b9-4904-8518-b8ff4ccd1e94', 12947.435),
    (253, 49.24317630, 9.13399490, 'Bad Wimpfen', 7, 'cc07fe0d-2e28-4288-afe3-5bedd8b5f76f', 12973.228),
    (254, 49.13805390, 9.39835740, 'Obersulm', 40, '2d7a347a-3eb2-4527-922e-7e77656b9009', 13048.191),
    (255, 49.11969310, 9.39561990, 'Obersulm', 40, '9af034b4-252f-422f-ad78-f5910c68281d', 13056.836),
    (256, 49.23351970, 9.32966720, 'Neuenstadt am Kocher', 37, 'b4e2d378-a833-4222-8355-4de1844ae92b', 13092.807),
    (257, 49.13789110, 9.39956280, 'Obersulm', 40, '63559918-2db2-408c-9f75-fdc192ac4eb7', 13136.282),
    (258, 49.08367223, 9.05971483, 'Brackenheim', 9, '3275aeee-20a3-469d-9423-4e59f8234946', 13210.955),
    (259, 49.04084180, 9.32075400, 'Beilstein', 8, '8c511758-6e75-459f-8fdf-29d3953ecfd7', 13337.546),
    (260, 49.26211660, 9.20361200, 'Gundelsheim', 20, '9de205dc-fea4-4545-a627-032e4fc2ae23', 13559.303),
    (261, 49.03566471, 9.31498861, 'Beilstein', 8, '290e923b-b752-460c-b8ce-8fd83f46a8a2', 13599.774),
    (262, 49.07748580, 9.05815580, 'Brackenheim', 9, 'cd5d05a1-fca8-4f8c-a504-4707889a0423', 13651.810),
    (263, 49.06616700, 9.06964510, 'Brackenheim', 9, 'b2777140-e9aa-450c-bf64-8be20ff2992c', 13665.965),
    (264, 49.24314440, 9.11408150, 'Bad Rappenau', 6, 'cf9fdc62-3d36-4d10-a17b-59d3eb5941c7', 13718.702),
    (265, 49.04058370, 9.33108620, 'Beilstein', 8, '7d72621a-97c9-45db-a4e5-0162f7c9a179', 13792.737),
    (266, 49.06123510, 9.36470780, 'Beilstein', 8, 'c623abc2-1d94-4ad6-a5f2-d2508e454bd0', 13796.382),
    (267, 49.23720090, 9.09985340, 'Bad Rappenau', 6, '854add3f-9ab6-4c31-8f07-bdf9d8cda23f', 13799.137),
    (268, 49.06340850, 9.07018310, 'Brackenheim', 9, '88eafacc-b318-436f-b3aa-5367aa5bd39f', 13823.374),
    (269, 49.24200640, 9.10656350, 'Bad Rappenau', 6, '0c6122c5-de73-42d7-9922-729740f9253d', 13927.175),
    (270, 49.23754330, 9.09651580, 'Bad Rappenau', 6, '33ce9fce-0b1d-49ac-9458-da6dbd10c58b', 13981.972),
    (271, 49.14167083, 9.41180147, 'Obersulm', 40, '5a1a21f9-c917-4f82-ade4-0fe8f27364d0', 14023.144),
    (272, 49.24213270, 9.09920020, 'Bad Rappenau', 6, '088623b8-b486-4e97-bb01-28dfa0f17ab6', 14258.892),
    (273, 49.26279810, 9.15175750, 'Bad Rappenau', 6, '67a8fef6-e27f-406a-b214-508cfd365832', 14441.071),
    (274, 49.23582310, 9.08234220, 'Bad Rappenau', 6, 'e67ad10d-a511-49ab-bcee-25b245a78a3a', 14519.461),
    (275, 49.25600090, 9.12187050, 'Bad Rappenau', 6, '8637812c-2851-4780-8ba4-5a2b9fdc1e88', 14646.638),
    (276, 49.24553250, 9.09499590, 'Bad Rappenau', 6, 'a2019dde-fbe8-4d24-bd74-73a041a90840', 14744.647),
    (277, 49.26352040, 9.29564430, 'Neuenstadt am Kocher', 37, '780c7cf5-08c4-49b8-842a-17ce4bb68ffa', 14758.853),
    (278, 49.09819660, 9.02552730, 'Brackenheim', 9, '1b69b3a4-bac5-41da-b134-4296d9c350fa', 14850.557),
    (279, 49.13198270, 9.01400860, 'Schwaigern', 45, '08f7d227-b2bc-48c9-9416-123990767ec3', 14946.354),
    (280, 49.09132490, 9.41066280, 'Löwenstein', 31, '08d6a6f6-4611-4981-b274-5154159a97ff', 14984.207),
    (281, 49.22675170, 9.05825630, 'Bad Rappenau', 6, 'f9bdc1cb-f2e8-4b4f-961b-ac17b07a7663', 15110.788),
    (282, 49.09270330, 9.41340350, 'Löwenstein', 31, '88219c9c-b4fb-4edb-a824-00efc8b30b44', 15115.185),
    (283, 49.13327120, 9.00685350, 'Schwaigern', 45, '33107df7-801e-447f-bfb4-0d53e8944411', 15457.451),
    (284, 49.06870350, 9.03027470, 'Güglingen', 19, 'de51b36f-018d-4a7b-9c8e-5e8d201a5e85', 15897.001),
    (285, 49.28009800, 9.16650200, 'Gundelsheim', 20, '991ecd1d-b54c-44f2-ae0f-2196339d5372', 15974.833),
    (286, 49.28371000, 9.16606700, 'Gundelsheim', 20, '6a18a84e-e866-49ee-b54d-35bc42bb2c7b', 16372.487),
    (287, 49.24350010, 9.05714960, 'Bad Rappenau', 6, '8224658a-c53b-4339-9bc7-7968aabeadf3', 16411.216),
    (288, 49.28554970, 9.15976870, 'Gundelsheim', 20, '65f3a931-4c34-4c08-a1de-edf187d74e80', 16683.528),
    (289, 49.11059440, 8.99057630, 'Schwaigern', 45, '182b4b75-2534-49bf-8b43-25bb7079eeb0', 16955.298),
    (290, 49.06906470, 9.00872040, 'Güglingen', 19, 'a29d7a73-2a2b-4c9a-9ed3-1c5eddb73df9', 17252.719),
    (291, 49.20264090, 8.99662860, 'Kirchardt', 23, '24a08cad-60f7-444b-ab00-36e9542bee83', 17579.106),
    (292, 49.18504090, 8.98596650, 'Kirchardt', 23, '9d5b0746-918f-4be3-a269-6d83ee895ada', 17652.699),
    (293, 49.02755610, 9.38999290, 'Spiegelberg', 46, 'd27c8b09-d1d4-4cbe-8140-9da736d9f11c', 17691.661),
    (294, 49.20398650, 8.99381140, 'Kirchardt', 23, '2043f72c-5ad3-4530-9057-ea90b04974a3', 17826.091),
    (295, 49.01445260, 9.37108810, 'Aspach', 3, '53bb8ea9-80ba-4a3e-aaa7-e1f593c0d1f6', 17871.474),
    (296, 49.06266690, 9.00278660, 'Güglingen', 19, '2f2e39f7-e21c-42b9-bf92-f62c3bd45e72', 17970.083),
    (297, 49.06871710, 8.99666690, 'Güglingen', 19, '877f14cc-a1e1-4eb6-8203-bcf56508a80b', 18053.039),
    (298, 49.25241580, 9.03847360, 'Bad Rappenau', 6, '5594d823-5747-46fb-9b8e-68145a125bd0', 18075.979),
    (299, 49.18371330, 8.97726170, 'Kirchardt', 23, 'a4a571bf-95ba-4173-b4cf-0d8f3605db58', 18222.011),
    (300, 49.03132930, 9.40862480, 'Spiegelberg', 46, '8e233882-4a11-4954-a27e-95149bec5121', 18391.277),
    (301, 49.09874890, 8.97440790, 'Eppingen', 14, '3221b0de-04a9-49cb-b7a1-c979e183cd71', 18400.556),
    (302, 49.10180960, 8.96910810, 'Eppingen', 14, '806b2afe-4d41-47b5-83ea-40891a9ece26', 18691.986),
    (303, 49.22846900, 8.99456750, 'Bad Rappenau', 6, '1d4158cc-5e32-4109-925a-98763161b966', 19016.628),
    (304, 49.06548720, 9.45497030, 'Spiegelberg', 46, '39c9aa91-b958-4fcd-b44a-ce73985feedd', 19098.707),
    (305, 48.99309320, 9.35344190, 'Aspach', 3, '9c084989-cffa-4857-9852-4ce2c68d73c1', 19101.813),
    (306, 49.07772740, 9.46346320, 'Wüstenrot', 53, 'cd471bd3-4bb6-4601-9920-0c22afc78a8e', 19116.053),
    (307, 49.28877460, 9.08287660, 'Hüffenhardt', 21, '7a8ea333-c22b-414c-a2c4-65ff97760d15', 19217.309),
    (308, 49.23833050, 9.43849430, 'Öhringen', 41, 'dd0fbf37-faed-4950-bafa-3932aeb0e96f', 19299.681),
    (309, 49.29292240, 9.08994910, 'Hüffenhardt', 21, '98beca32-3d7b-4d69-9217-e721c2bcf9b2', 19360.066),
    (310, 49.28919850, 9.07813650, 'Hüffenhardt', 21, 'a392d27c-a617-4292-b0c5-869299fe7390', 19436.775),
    (311, 48.98963830, 9.35821070, 'Aspach', 3, '64ea0179-3136-441b-91a1-e58a758b7ccf', 19610.203),
    (312, 48.99133420, 9.36874270, 'Aspach', 3, 'ce4a675b-41cb-4839-8c43-c78e53b5dc59', 19859.768),
    (313, 49.04090380, 9.44567130, 'Spiegelberg', 46, '160134b4-0688-4c42-9e47-0e7d7839b6d7', 19880.342),
    (314, 49.02990620, 9.43935000, 'Spiegelberg', 46, 'b94eea91-20ee-4d84-af2e-c1cb6f7dd435', 20221.527),
    (315, 49.12730130, 9.49723500, 'Wüstenrot', 53, '15261dbe-04f9-4520-be62-321f3c237f2e', 20294.172),
    (316, 49.19112836, 9.48753790, 'Öhringen', 41, 'c6027c70-9e3c-4e24-9ec9-78be5cdc5056', 20314.876),
    (317, 48.99588070, 9.39568410, 'Aspach', 3, 'bca6d43a-1a03-4c34-91f0-ba318fdac392', 20604.322),
    (318, 49.20588964, 9.48700660, 'Öhringen', 41, '5aa92c11-55ff-469f-9d00-b29152815bd3', 20789.792),
    (319, 49.04978030, 9.46983370, 'Spiegelberg', 46, '93a287e2-01f4-4560-821c-9f2b634c87af', 20866.939),
    (320, 49.20081440, 9.49562670, 'Öhringen', 41, 'a93b3aa3-5fb7-4873-a66c-60f1beff6280', 21194.058),
    (321, 49.12047770, 9.50992540, 'Wüstenrot', 53, '6c2b3d53-2059-4fe3-b8f6-360b852d3e4b', 21282.870),
    (322, 49.29095880, 9.03481790, 'Bad Rappenau', 6, 'ebe3e035-ac4a-499a-9147-1cb86864be14', 21414.735),
    (323, 49.13152280, 8.92270740, 'Eppingen', 14, 'fd743ef1-187b-4205-926b-9692aaa991d6', 21581.548),
    (324, 49.20613600, 9.49859660, 'Öhringen', 41, 'f226776c-2e51-4080-92c5-19132b380926', 21590.477),
    (325, 49.13960133, 8.91872819, 'Eppingen', 14, 'b3a0444a-a989-457e-93e9-bac2b780a989', 21845.963),
    (326, 48.98774860, 9.40983680, 'Aspach', 3, '20700d95-ee03-4d69-af94-82b69f3481e8', 21956.499),
    (327, 49.06376490, 9.49976670, 'Großerlach', 18, 'deea729c-5db1-4a96-8d41-0d7e2f412807', 22151.136),
    (328, 48.94185770, 9.18739860, 'Freiberg am Neckar', 17, 'dd3a9c61-4054-4c09-9875-4b4c8d1db12f', 22218.209),
    (329, 49.19773780, 9.51204260, 'Öhringen', 41, 'b5091ecc-9d9f-44d9-8d34-b89013cd0352', 22229.978),
    (330, 49.31911020, 9.35798450, 'Möckmühl', 33, 'da2dd908-03b0-4312-8dbb-22db9d4a65b1', 22267.400),
    (331, 49.32351820, 9.34911500, 'Möckmühl', 33, '12f84298-f6ed-44f0-8327-bdde1834e16d', 22426.480),
    (332, 49.32032260, 9.36193040, 'Möckmühl', 33, '1c458368-007b-474e-8cb0-61880caaeed5', 22518.187),
    (333, 49.02116520, 9.46899630, 'Sulzbach an der Murr', 47, '63288317-a2aa-4841-9fa8-41c8f7234bf5', 22533.981),
    (334, 49.03243740, 9.48137950, 'Sulzbach an der Murr', 47, '80f9597e-78ff-49ce-a8a5-e8e58a54e951', 22574.999),
    (335, 48.97013790, 9.38738290, 'Aspach', 3, '35094b09-e0fe-4292-89e6-0bfa326f496b', 22577.225),
    (336, 49.14067480, 8.90684370, 'Eppingen', 14, 'b64b3534-2bab-4b35-ad5a-02642de945e4', 22709.976),
    (337, 49.32226140, 9.36456380, 'Möckmühl', 33, 'da8f633f-3467-4a68-89ce-519b1b2e6871', 22797.643),
    (338, 48.93610160, 9.19065890, 'Freiberg am Neckar', 17, '30217a75-b1f1-4937-aec1-0586c57b2dd4', 22832.157),
    (339, 49.13645960, 8.90507710, 'Eppingen', 14, '6137ae44-5eb4-4d91-b96d-15a0ec8b3385', 22844.077),
    (340, 49.32088580, 9.06726970, 'Hüffenhardt', 21, 'bf16ec5f-0bdb-4efd-a5db-14c165d51e4e', 22876.830),
    (341, 49.13189330, 8.90164940, 'Eppingen', 14, 'ec4fce70-03f4-4f15-997f-9e24346964ed', 23110.124),
    (342, 49.33814150, 9.12006120, 'Mosbach', 34, 'aad6e14c-820c-4fb3-8521-cc43ad6768c4', 23111.815),
    (343, 49.19889370, 9.52622200, 'Öhringen', 41, 'b800c38b-e3c3-4d77-a2db-cb0f85505a70', 23254.960),
    (344, 49.34196320, 9.13126890, 'Mosbach', 34, 'eec48f0f-805c-4c56-ae87-9163c7bfb0d7', 23280.294),
    (345, 49.20207580, 9.52520150, 'Öhringen', 41, 'f523de30-e85e-4c02-99db-9d9046658211', 23284.455),
    (346, 48.95528960, 9.36839220, 'Kirchberg an der Murr', 24, '5eaf9697-44ec-427c-9b9e-d08f959f0276', 23303.260),
    (347, 48.96927280, 9.40340810, 'Aspach', 3, '106573a6-3704-4543-a741-7af7f7ecfc27', 23311.031),
    (348, 49.09884610, 8.90265940, 'Eppingen', 14, 'f5412446-ccdf-49d8-9f69-cde919e2c803', 23487.337),
    (349, 49.19895820, 9.52959490, 'Öhringen', 41, 'e0aa3987-693f-485f-86e6-79a4530b8405', 23492.519),
    (350, 49.05155880, 9.51269400, 'Großerlach', 18, '63c4f3e9-8b8c-4467-93f3-9ea502ccd174', 23562.057),
    (351, 49.34282192, 9.12012308, 'Mosbach', 34, 'd74a0472-df66-47d0-b6a2-dec11e14b16d', 23605.547),
    (352, 48.94022300, 9.32883580, 'Kirchberg an der Murr', 24, '60f6186d-d2f3-4b1c-98d2-969d81aed970', 23673.962),
    (353, 48.92834400, 9.18769780, 'Freiberg am Neckar', 17, 'a5c80d1b-52d5-4730-a171-ac8fa48f87d6', 23711.182),
    (354, 49.16513260, 8.89342510, 'Eppingen', 14, 'a48ac8c1-fcf4-4e45-9df0-e44dd9a6b8b5', 23836.961),
    (355, 49.34992620, 9.14602840, 'Mosbach', 34, '541f1708-e7ba-42a4-95c6-2e2cc0a873cf', 23872.555),
    (356, 49.34721630, 9.12966120, 'Mosbach', 34, 'd2b214f9-5a13-4a53-9aff-c587c2cf3cda', 23874.007),
    (357, 48.94255710, 9.35272580, 'Kirchberg an der Murr', 24, '312ddd94-3197-47a5-a915-158c7e46b6f9', 24080.306),
    (358, 48.93526440, 9.32457010, 'Kirchberg an der Murr', 24, 'f38d7ce1-ac9d-4640-a841-c7f594a9d76e', 24092.634),
    (359, 49.34399260, 9.10395010, 'Mosbach', 34, 'd4d990e2-5738-400d-96f7-de8b71273a20', 24110.806),
    (360, 48.99333620, 9.46312380, 'Oppenweiler', 43, '3fd57127-c44b-4fc2-ade7-ce8b8c9ecd60', 24172.896),
    (361, 48.98945150, 9.45944780, 'Oppenweiler', 43, '07358f0b-74d3-4ca2-a580-e0bda5790de1', 24274.112),
    (362, 49.27843410, 9.47841120, 'Forchtenberg', 16, '21f55b72-0de5-4549-8052-8ef2e8803df2', 24288.846),
    (363, 48.98247020, 9.45103840, 'Oppenweiler', 43, '8c05ce35-d71b-4ddc-a16d-7dbbd9d18a1f', 24390.181),
    (364, 48.98586540, 9.45807890, 'Oppenweiler', 43, 'faa8ce25-ebb8-45c6-853a-f6091aac6a72', 24481.272),
    (365, 48.97566140, 9.44216820, 'Backnang', 4, '43d5954f-b3f6-42c4-adfc-279b357b6eeb', 24508.811),
    (366, 48.97246190, 9.43712740, 'Backnang', 4, 'faadaf1c-7df9-4499-beeb-b0e28b2514bf', 24537.014),
    (367, 49.03241080, 9.51575820, 'Sulzbach an der Murr', 47, '5b62ed9c-3b23-4ac9-8d79-77ff29d8e746', 24731.183),
    (368, 48.97598600, 9.44790590, 'Backnang', 4, '69cf3dc2-cca4-470d-85f2-6df2887955ef', 24761.402),
    (369, 48.98580480, 9.46399890, 'Oppenweiler', 43, '3eb1dd51-aa70-453f-a813-82a0a2decb9f', 24794.655),
    (370, 49.00615950, 9.49160590, 'Sulzbach an der Murr', 47, '728951b0-b56d-41f7-9b73-8599baf3b4dc', 24852.920),
    (371, 48.91911090, 9.17253690, 'Ludwigsburg', 32, 'dc0175f2-e693-45bf-abcf-120b49e3a0cd', 24859.769),
    (372, 48.98233870, 9.46061870, 'Oppenweiler', 43, 'dac73d0b-e6e9-452d-bf93-78280892f633', 24889.395),
    (373, 48.94749750, 9.39618300, 'Backnang', 4, '9ae32018-508d-4f3c-ab51-c1df353c1c9d', 25054.349),
    (374, 49.36130770, 9.14687190, 'Mosbach', 34, 'd4f96c16-ab29-4a4b-aae0-0bd43639c2c1', 25095.136),
    (375, 48.97841820, 9.45955370, 'Oppenweiler', 43, 'c21a6282-1f83-4f6f-ab35-08c491bff3a3', 25145.833),
    (376, 48.95630000, 9.42047740, 'Backnang', 4, '88bc1c8c-fcc1-447c-a476-4b018bea5278', 25208.531),
    (377, 49.17581150, 9.56260920, 'Öhringen', 41, 'c58a7ee1-107b-4cf8-9c86-ee4eed5d8335', 25289.353),
    (378, 49.35560390, 9.10509880, 'Mosbach', 34, '6af9eb67-0689-4049-a11b-b2882c3d9aee', 25298.185),
    (379, 49.00255290, 9.49530530, 'Sulzbach an der Murr', 47, '7238f408-30ab-4272-a7bb-4fedc4e86db2', 25310.487),
    (380, 48.95867710, 9.42825040, 'Backnang', 4, '4f1f61d4-b04a-473a-ba7d-83456e1c305a', 25330.811),
    (381, 49.05392990, 9.54124100, 'Großerlach', 18, 'f110fbce-20a8-477e-893e-988e5781fa50', 25361.294),
    (382, 49.04251930, 9.53394200, 'Großerlach', 18, 'd94e7639-4afe-43eb-8ab8-61f8fd7d9397', 25391.493),
    (383, 48.95308070, 9.41888620, 'Backnang', 4, 'abbc56bc-44c1-4810-8996-18884536b11a', 25434.064),
    (384, 49.13351830, 8.86790220, 'Eppingen', 14, '1cef2a7e-349a-4c9e-9f5d-cfb65891a7d8', 25556.688),
    (385, 49.00132430, 9.49827090, 'Sulzbach an der Murr', 47, 'b59b66b5-cf8c-4ed3-8c8c-35af7cd1d0d6', 25565.317),
    (386, 48.95749190, 9.43248130, 'Backnang', 4, '68bc7154-ed22-4f09-90b2-9c04c3547139', 25622.303),
    (387, 48.95269910, 9.42321260, 'Backnang', 4, '390bc7ea-7f7a-49a7-964c-24a226e2008d', 25650.525),
    (388, 48.93014720, 9.36539650, 'Burgstetten', 10, '4ef02249-5a2a-4d92-833d-d5c28a3493f9', 25718.071),
    (389, 48.95036010, 9.41993710, 'Backnang', 4, 'f1e634ef-0b55-4944-8b78-c4aec124798c', 25726.387),
    (390, 48.91008470, 9.17979280, 'Ludwigsburg', 32, '480a1067-c461-4f36-894c-40772dcdad27', 25790.425),
    (391, 48.90991950, 9.17755220, 'Ludwigsburg', 32, '900356cd-c043-4b11-b008-345f667fcddd', 25827.303),
    (392, 48.95034290, 9.42336270, 'Backnang', 4, '83316d1f-c060-44d2-b6db-4739c2d221fb', 25870.871),
    (393, 49.00474790, 9.50808840, 'Sulzbach an der Murr', 47, '1077caac-cd7d-4730-94c3-c7773e37f93f', 25913.623),
    (394, 48.94740540, 9.41915970, 'Backnang', 4, '571dfd3c-190f-453b-8750-e9e8b01ca0e8', 25965.571),
    (395, 48.92899850, 9.37098100, 'Burgstetten', 10, '95f97f39-766c-4d8d-82e1-6ac5e9a85e40', 26005.175),
    (396, 48.95416790, 9.43573680, 'Backnang', 4, '85a7a4e7-d154-4ef9-b049-4c9c295d09f6', 26060.387),
    (397, 48.95189260, 9.43118690, 'Backnang', 4, 'cb20cfec-d921-4b8e-80da-8d0102859c4c', 26064.219),
    (398, 49.00487210, 9.51379280, 'Sulzbach an der Murr', 47, '63fd14f9-e591-4840-9734-39d459402a3d', 26244.410),
    (399, 48.90601780, 9.17901530, 'Ludwigsburg', 32, '33812aa9-edfe-4d88-95e4-2caaaa5ac3c1', 26246.156),
    (400, 48.92733460, 9.37460040, 'Burgstetten', 10, '14a6c18d-5ccc-4395-9490-1600098fce48', 26285.524),
    (401, 48.94717060, 9.42720030, 'Backnang', 4, 'a6e49809-f62a-481a-8c9e-28722e3758cd', 26320.607),
    (402, 49.20460440, 9.56844540, 'Neuenstein', 38, 'fd6cd941-9277-4c89-bb86-8cead0e19daa', 26379.720),
    (403, 48.90440520, 9.17134010, 'Ludwigsburg', 32, 'f588aa37-30f2-460b-bcaa-15e74f5fade7', 26492.011),
    (404, 48.95157120, 9.44034660, 'Backnang', 4, 'e8b7801e-06d5-4393-8f69-2d24b80b7581', 26494.085),
    (405, 48.94207080, 9.42069610, 'Backnang', 4, '7b687162-ab53-4f5b-ac3a-461bde75ff7c', 26520.744),
    (406, 48.95411140, 9.44681230, 'Backnang', 4, 'ba1a34a3-3b59-4167-8f38-a6f7e2992d90', 26562.246),
    (407, 49.00157960, 9.51611340, 'Sulzbach an der Murr', 47, 'c08e640d-4a83-40d1-954c-92d0d0392046', 26594.584),
    (408, 48.94804960, 9.43818290, 'Backnang', 4, 'caa08c4c-e55f-4b9c-9d39-ffeb879c263d', 26711.538),
    (409, 48.94344940, 9.42879690, 'Backnang', 4, '9f72232a-39f1-4ff2-94d5-173d6421d658', 26726.512),
    (410, 48.95037310, 9.44481400, 'Backnang', 4, '4e8cb906-f0b5-4134-b83d-f17cd16bf044', 26798.707),
    (411, 49.20317700, 9.57509580, 'Neuenstein', 38, '152f8dae-3aed-4a29-bfd5-74c8c1a64cee', 26804.284),
    (412, 48.92692280, 9.38958710, 'Burgstetten', 10, '526ce797-6842-4cf2-b503-4f54cb34a5c9', 26815.633),
    (413, 49.20607890, 9.57467970, 'Neuenstein', 38, '90931238-e129-4d26-916d-cb441e0c7d04', 26860.018),
    (414, 48.95484090, 9.45477070, 'Backnang', 4, '807b5146-7559-4c5a-b646-ffc180a04314', 26866.055),
    (415, 48.89895220, 9.20602360, 'Ludwigsburg', 32, 'd52770bd-63d0-4c1c-bd49-83606f49beba', 26885.849),
    (416, 48.98816630, 9.50604560, 'Sulzbach an der Murr', 47, 'dd716fc5-44b7-4ec8-8577-698872b70953', 26916.877),
    (417, 48.92594980, 9.39083520, 'Burgstetten', 10, 'b9935050-2b38-43ba-9368-a95d5db228eb', 26953.755),
    (418, 48.94547930, 9.43852350, 'Backnang', 4, '540c6c27-b775-4d9f-90e2-2586fcae7b78', 26956.127),
    (419, 48.94144100, 9.43009840, 'Backnang', 4, '25ccbe9e-51fb-4fc5-ad3a-709a8f82b859', 26964.175),
    (420, 48.95136820, 9.45085870, 'Backnang', 4, '77c7ffe0-a881-4741-b938-8b6f422f3012', 26984.995),
    (421, 48.96709749, 9.47966699, 'Backnang', 4, '9535ef28-3842-496c-b26f-f8ebc0232e7c', 27072.007),
    (422, 49.38304240, 9.18327080, 'Elztal', 13, 'ac74d765-54d2-45df-b134-f4a83225a77b', 27083.885),
    (423, 48.91815780, 9.37165500, 'Burgstetten', 10, 'ca72f466-eb0a-4684-bd14-ae63f92a038a', 27121.265),
    (424, 48.94177050, 9.43710950, 'Backnang', 4, '897f72d7-0065-45dc-8b98-c9a0bc84bcbe', 27229.196),
    (425, 48.94158060, 9.43904590, 'Backnang', 4, 'a5661249-cbb7-4a1b-b374-0f58adada00b', 27328.945),
    (426, 48.93848690, 9.43395770, 'Backnang', 4, 'a5d7e223-6a27-4dc1-b656-99929861d78d', 27394.743),
    (427, 49.01361890, 9.54207680, 'Sulzbach an der Murr', 47, '947ac6b2-ff4e-434c-8513-71ed39c37ae9', 27440.521),
    (428, 48.89794760, 9.29405800, 'Remseck am Neckar', 44, '52162d37-15a8-4071-b507-d1d2e0126310', 27529.903),
    (429, 48.95698520, 9.47548320, 'Backnang', 4, 'cc7add64-478d-4175-b2ec-a4b4f5b65a70', 27678.969),
    (430, 49.21333350, 9.58344040, 'Neuenstein', 38, '1e568f2b-7a0d-4e35-934c-14b6619d284c', 27696.451),
    (431, 48.95828890, 9.47912380, 'Backnang', 4, '924dcdd0-4f87-4cee-a721-1ea3d1531c22', 27752.580),
    (432, 48.93084410, 9.42680910, 'Backnang', 4, '58680f30-1b2b-4bdd-986f-1267498e0773', 27809.551),
    (433, 48.92917090, 9.42421230, 'Backnang', 4, 'bbfd5d10-26b2-42bb-8ea4-507fe1d32a5a', 27863.832),
    (434, 48.89046870, 9.19393150, 'Ludwigsburg', 32, '8fa8232c-9a47-4a4b-af83-2bd50de17ed9', 27872.609),
    (435, 49.17377750, 8.83795710, 'Eppingen', 14, 'f2665c68-6f0f-425d-b8d2-7bd49d1f6b67', 27956.407),
    (436, 48.94438650, 9.45938250, 'Backnang', 4, '5634d6a1-dbbe-4dce-b4d6-6b7ada735570', 27980.058),
    (437, 48.92709600, 9.42230220, 'Backnang', 4, '1c90f2a5-7094-4f68-b83e-18b95a7a4f0b', 27984.948),
    (438, 48.93663650, 9.44400130, 'Backnang', 4, 'b282037d-c43f-48a9-bfcb-d985ab4df899', 27986.547),
    (439, 48.91220140, 9.38212400, 'Leutenbach', 30, '0918ff7e-8da0-4886-bd35-4641d4110270', 28041.938),
    (440, 49.07994260, 8.84498680, 'Kürnbach', 26, 'fa2fbc26-5820-4960-b335-d14461af30e5', 28049.146),
    (441, 49.17974520, 8.83733210, 'Eppingen', 14, 'ac35b077-475a-4894-986f-6d83de559c42', 28094.955),
    (442, 48.92537780, 9.42278190, 'Backnang', 4, '49a06e00-0bce-424f-91d4-19fc605b2ab7', 28165.763),
    (443, 48.99471830, 9.53529460, 'Sulzbach an der Murr', 47, '1aa576aa-ce2c-4113-8218-cbf68f6ba87c', 28176.994),
    (444, 48.89387230, 9.30851570, 'Waiblingen', 51, '2f911476-3001-4506-9a32-fdfd5635f18a', 28199.372),
    (445, 48.89419820, 9.31205130, 'Waiblingen', 51, '71af2928-a649-4ab4-a52e-2ae34b401909', 28224.967),
    (446, 49.07355920, 8.84226790, 'Kürnbach', 26, '2b294f65-3611-49ba-b10d-2be9cada039d', 28420.844),
    (447, 48.89340520, 9.31882310, 'Waiblingen', 51, '443e484a-0fcf-4352-bc53-fe1e19e1bd68', 28432.949),
    (448, 49.07752330, 8.83959820, 'Kürnbach', 26, '504a2281-e5ea-417d-a731-92f1ff23eebe', 28495.689),
    (449, 48.88623040, 9.17033190, 'Ludwigsburg', 32, '7dcc7ad1-bb5a-499b-a513-f554ed3d246d', 28505.849);

CREATE TEMP TABLE proposal_checks (
    description TEXT NOT NULL,
    passed INTEGER NOT NULL CHECK (passed = 1)
);

INSERT OR ROLLBACK INTO proposal_checks
SELECT 'Expected 449 existing synthetic locations',
       CASE WHEN COUNT(*) = 449 AND SUM(is_synthetic = 1) = 449
            THEN 1 ELSE 0 END
FROM locations;

INSERT OR ROLLBACK INTO proposal_checks
SELECT '449 proposed points with contiguous IDs and complete provenance',
       CASE WHEN COUNT(*) = 449 AND MIN(point_id) = 1 AND MAX(point_id) = 449
                 AND COUNT(s.source_id) = 449
            THEN 1 ELSE 0 END
FROM proposed_points AS p
LEFT JOIN coordinate_sources AS s USING (source_id);

INSERT OR ROLLBACK INTO proposal_checks
SELECT '109 Heilbronn points and 340 additional regional points',
       CASE WHEN SUM(s.source_kind = 'official_heilbronn') = 109
                 AND SUM(s.source_kind = 'regional_glass_map') = 340
            THEN 1 ELSE 0 END
FROM proposed_points AS p
JOIN coordinate_sources AS s USING (source_id);

CREATE TEMP TABLE proposed_locations AS
WITH ordered_ids AS (
    SELECT location_id,
           ROW_NUMBER() OVER (ORDER BY location_id) AS point_id
    FROM locations
)
SELECT ids.location_id, p.*, s.source_kind, s.source_url
FROM ordered_ids AS ids
JOIN proposed_points AS p USING (point_id)
JOIN coordinate_sources AS s USING (source_id);

-- Review all old/new positions, municipality labels and coordinate sources.
SELECT p.point_id, p.location_id, p.municipality,
       l.latitude AS old_latitude, l.longitude AS old_longitude,
       p.latitude AS proposed_latitude, p.longitude AS proposed_longitude,
       ROUND(p.distance_from_heilbronn_metres / 1000.0, 2) AS radius_km,
       p.source_kind, p.source_url, p.source_reference,
       1 AS is_synthetic
FROM proposed_locations AS p
JOIN locations AS l USING (location_id)
ORDER BY p.point_id;

SELECT municipality, COUNT(*) AS proposed_location_count
FROM proposed_locations
GROUP BY municipality
ORDER BY proposed_location_count DESC, municipality;

-- Proposed update, for a separate demo copy only.
UPDATE locations
SET latitude = (
        SELECT p.latitude FROM proposed_locations AS p
        WHERE p.location_id = locations.location_id
    ),
    longitude = (
        SELECT p.longitude FROM proposed_locations AS p
        WHERE p.location_id = locations.location_id
    ),
    is_synthetic = 1
WHERE location_id IN (SELECT location_id FROM proposed_locations);

SELECT changes() AS locations_matched; -- expected: 449

-- Discard the demonstrated update and all temporary tables.
ROLLBACK;
```

## Proposed count by municipality label

These labels are supplied by the source listings; they have not been checked against administrative boundary polygons. They do not change the database schema or add a municipality column to `locations`.

| Municipality label | Synthetic points |
| --- | ---: |
| Heilbronn | 109 |
| Backnang | 37 |
| Bad Rappenau | 16 |
| Brackenheim | 14 |
| Neckarsulm | 14 |
| Obersulm | 14 |
| Lauffen am Neckar | 13 |
| Eppingen | 12 |
| Sulzbach an der Murr | 12 |
| Untergruppenbach | 12 |
| Schwaigern | 10 |
| Öhringen | 10 |
| Bad Wimpfen | 9 |
| Aspach | 8 |
| Ludwigsburg | 8 |
| Mosbach | 8 |
| Bad Friedrichshall | 7 |
| Ilsfeld | 7 |
| Nordheim | 7 |
| Oppenweiler | 7 |
| Burgstetten | 6 |
| Löwenstein | 6 |
| Spiegelberg | 6 |
| Beilstein | 5 |
| Leingarten | 5 |
| Weinsberg | 5 |
| Flein | 4 |
| Großerlach | 4 |
| Gundelsheim | 4 |
| Güglingen | 4 |
| Hüffenhardt | 4 |
| Kirchardt | 4 |
| Kirchberg an der Murr | 4 |
| Möckmühl | 4 |
| Neckarwestheim | 4 |
| Neuenstein | 4 |
| Offenau | 4 |
| Abstatt | 3 |
| Eberstadt | 3 |
| Ellhofen | 3 |
| Freiberg am Neckar | 3 |
| Kürnbach | 3 |
| Lehrensteinsfeld | 3 |
| Neuenstadt am Kocher | 3 |
| Talheim | 3 |
| Untereisesheim | 3 |
| Waiblingen | 3 |
| Wüstenrot | 3 |
| Elztal | 1 |
| Forchtenberg | 1 |
| Kirchheim am Neckar | 1 |
| Leutenbach | 1 |
| Remseck am Neckar | 1 |
| **Total** | **449** |
