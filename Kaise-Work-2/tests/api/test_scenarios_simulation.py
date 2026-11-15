"""POST /api/scenarios + POST /api/simulation — docs/contracts.md §5.2.4/§5.2.5.

Synthetic fixture (labelled ``loc-sim`` ids, never real data). Hand-reckoned
pins; arithmetic in comments. Simulation core: ``src.collection.simulation``
(rates VERBATIM from the §5.2.3 days-to-full rows; flat-mode §4.4 physics).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

SIM_CSV = """Location_id,material_type,date,fill_level_perc
loc-sim,green,2026-01-01,0
loc-sim,green,2026-01-05,20
loc-sim-1,brown,2026-01-03,10
"""

# loc-sim green: rate = 20 % / (2026-01-05 - 2026-01-01 = 4 d) = 5.0 pp/day
# (§5.2.3 median over the single rate candidate). loc-sim-1 brown: 1 record
# -> no rate (not_enough_records) -> skipped from the replay, reported with
# its reason (§4.4).
#
# §5.2.5 replay initialisation: per-series clock = last record date
# <= start_date (start = date_min 2026-01-01). loc-sim green's prior record
# IS 2026-01-01 (the fill-0 row), so its clock starts 2026-01-01 — NOT at
# the globally-latest 2026-01-05 record (which lies after the window start
# and must not inform the replay; leakage rule 6).

FREQUENCY_DAYS = 3
SIMULATION_DAYS = 12
# Window: start = date_min 2026-01-01, end = +11 d = 2026-01-12 (12 days).
# fixed_frequency due iff days_since >= 3 from the clock start 2026-01-01:
#   01-01 (0 d, fill 0), 01-02 (5), 01-03 (10); 01-04 (3 d, 15) DUE (reset);
#   01-05 (5), 01-06 (10); 01-07 (3 d, 15) DUE (reset);
#   01-08 (5), 01-09 (10); 01-10 (3 d, 15) DUE (reset);
#   01-11 (5), 01-12 (10).
# Emptyings: 01-04, 01-07, 01-10, fill at emptying 5 x 3 = 15.0 each.
# One stop per day: 3000 L x 15 % = 450 L (fits one truck), 10 min leg +
# 5 min service = 15 min (fits the 480 min shift) -> truck_days 3 x 1 = 3.
# cost_eur_total = 3 x 500.0 = 1500.0;
# cost_eur_per_year = round(1500.0 / 12 x 200, 2) = 25000.0.
# Max END-OF-DAY fill: due days reset to 0, so the max is 5 x 2 = 10.0
# (01-03 / 01-06 / 01-09 / 01-12); overflow 0 container-days -> 0.0 %;
# full-or-overfull emptyings 0/3 -> 0.0 %.


def _post(client: TestClient, path: str, body: dict) -> dict:
    response = client.post(path, json=body)
    assert response.status_code == 200, response.text
    return response.json()


def _upload(client: TestClient, content: str = SIM_CSV) -> None:
    response = client.post(
        "/api/datasets",
        files={"file": ("sim.csv", content.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 200, response.text


def test_scenarios_404_without_dataset(client: TestClient) -> None:
    response = client.post("/api/scenarios", json={})
    assert response.status_code == 404
    assert "dataset" in response.json()["detail"].lower()


def test_simulation_404_without_dataset(client: TestClient) -> None:
    response = client.post("/api/simulation", json={})
    assert response.status_code == 404
    assert "dataset" in response.json()["detail"].lower()


def test_empty_dataset_is_422(client: TestClient) -> None:
    upload = client.post(
        "/api/datasets",
        files={
            "file": (
                "header-only.csv",
                b"Location_id,material_type,date,fill_level_perc\n",
                "text/csv",
            )
        },
    )
    assert upload.status_code == 200, upload.text
    for path in ("/api/scenarios", "/api/simulation"):
        response = client.post(path, json={})
        assert response.status_code == 422, response.text
        assert "no rows" in response.json()["detail"]


def test_invalid_routing_override_is_422(client: TestClient) -> None:
    """frequency_days=0 fails the RoutingConfig constructor (§5.3: the
    domain validation message surfaces on 422)."""
    _upload(client)
    response = client.post("/api/scenarios", json={"routing_config": {"frequency_days": 0}})
    assert response.status_code == 422, response.text
    assert "frequency_days" in response.json()["detail"]


def test_non_flat_travel_mode_is_422(client: TestClient) -> None:
    """§5.2.4: the replay is flat-mode (§4.4); haversine_derived is a
    routing-only mode -> 422, never silently ignored."""
    _upload(client)
    response = client.post(
        "/api/simulation", json={"routing_config": {"travel_time_mode": "haversine_derived"}}
    )
    assert response.status_code == 422, response.text
    assert "fixed_per_leg" in response.json()["detail"]


def test_non_uniform_densities_are_422(client: TestClient) -> None:
    """§5.2.4: the fill->weight arithmetic takes ONE uniform density ->
    422 on per-material densities."""
    _upload(client)
    densities = {"brown": 0.4, "green": 0.5, "white": 0.4}
    response = client.post(
        "/api/scenarios", json={"routing_config": {"densities_kg_per_litre": densities}}
    )
    assert response.status_code == 422, response.text
    assert "uniform" in response.json()["detail"]


def test_scenarios_strategies_hand_reckoned(client: TestClient) -> None:
    _upload(client)
    body = _post(
        client,
        "/api/scenarios",
        {"frequency_days": FREQUENCY_DAYS, "simulation_days": SIMULATION_DAYS},
    )
    strategies = {strategy["id"]: strategy for strategy in body["strategies"]}
    assert set(strategies) == {"fixed_frequency", "demand_driven"}

    fixed = strategies["fixed_frequency"]
    # Arithmetic: see module block (3 emptyings -> 3 truck-days).
    assert fixed["stops_total"] == 3  # 01-04, 01-07, 01-10
    assert fixed["truck_days"] == 3  # 1 stop per day fits one truck
    assert fixed["cost_eur_total"] == 1500.0  # 3 x 500.0
    assert fixed["cost_eur_per_year"] == 25000.0  # round(1500.0 / 12 x 200, 2)
    service = fixed["service"]
    assert service["basis"] == "simulated"
    assert service["overflow_share_pct"] == 0.0  # max fill 15 <= 100
    assert service["share_emptyings_full_or_overfull_pct"] == 0.0  # 0 of 3
    # max_fill_pct is the max END-OF-DAY fill (§5.2.5): due days reset to 0,
    # so the max is 5 pp/day x 2 d = 10.0, not the 15 at emptying.
    assert service["max_fill_pct"] == 10.0

    demand = strategies["demand_driven"]
    # Threshold 80 (§3.1 default): the fill never resets (no emptyings) and
    # climbs to 5 pp/day x 11 d (01-12 vs clock start 01-01) = 55.0 < 80 ->
    # never due; no fabricated work (cost and stops honestly 0).
    assert demand["stops_total"] == 0
    assert demand["truck_days"] == 0
    assert demand["cost_eur_total"] == 0.0
    assert demand["cost_eur_per_year"] == 0.0
    assert demand["service"]["overflow_share_pct"] == 0.0  # 55 <= 100
    assert demand["service"]["share_emptyings_full_or_overfull_pct"] is None  # no emptyings
    assert demand["service"]["max_fill_pct"] == 55.0

    # Observed anchor over the fixture's 3 records: none >= 100/overfull
    # -> 0.0 %; max numeric fill 20.0 (loc-sim 2026-01-05).
    anchor = body["observed_anchor"]
    assert anchor["basis"] == "observed_emptying_records"
    assert anchor["share_full_or_overfull_pct"] == 0.0
    assert anchor["max_fill_pct"] == 20.0

    # loc-sim-1 brown: single record -> skipped with its §5.2.3 reason.
    assert body["skipped_series"] == [
        {"location_id": "loc-sim-1", "material_type": "brown", "reason": "not_enough_records"}
    ]

    echo = body["config_echo"]
    assert echo["frequency_days"] == FREQUENCY_DAYS
    assert echo["simulation_days"] == SIMULATION_DAYS
    assert echo["select_threshold_pct"] == 80.0
    assert echo["travel_time_mode"] == "fixed_per_leg"
    assert any(
        label == "simulation based on historical rates, not a prediction of reality"
        for label in body["assumptions"]
    )


def test_simulation_days_hand_reckoned(client: TestClient) -> None:
    _upload(client)
    body = _post(
        client,
        "/api/simulation",
        {"frequency_days": FREQUENCY_DAYS, "simulation_days": SIMULATION_DAYS},
    )
    assert body["start_date"] == "2026-01-01"  # dataset date_min
    assert body["end_date"] == "2026-01-12"  # start + 12 - 1
    assert body["data_basis"] == {"records": "observed", "rates": "derived", "plan": "simulated"}

    strategies = {strategy["id"]: strategy for strategy in body["strategies"]}
    fixed_days = strategies["fixed_frequency"]["days"]
    assert len(fixed_days) == 12  # one record per replayed day
    by_date = {record["date"]: record for record in fixed_days}
    # Emptying days (see module arithmetic): 01-04, 01-07, 01-10.
    assert by_date["2026-01-04"] == {
        "date": "2026-01-04",
        "collections": 1,
        "overflow_containers": 0,
        "truck_days": 1,
        "cumulative_cost_eur": 500.0,
    }
    assert by_date["2026-01-07"]["collections"] == 1
    assert by_date["2026-01-07"]["cumulative_cost_eur"] == 1000.0
    assert by_date["2026-01-10"]["collections"] == 1
    assert by_date["2026-01-10"]["cumulative_cost_eur"] == 1500.0
    quiet = by_date["2026-01-05"]
    assert quiet["collections"] == 0 and quiet["truck_days"] == 0
    assert quiet["cumulative_cost_eur"] == 500.0  # running total carries

    demand_days = strategies["demand_driven"]["days"]
    assert len(demand_days) == 12
    assert all(record["collections"] == 0 for record in demand_days)  # never >= 80
    assert all(record["cumulative_cost_eur"] == 0.0 for record in demand_days)

    # Calibration: simulated fills at emptying [15, 15] -> median 15.0;
    # observed numeric fills [0, 10, 20] -> median 10.0 (§5.2.5).
    calibration = body["calibration"]
    assert calibration["simulated_fill_at_emptying_median_pct"] == 15.0
    assert calibration["observed_fill_at_emptying_median_pct"] == 10.0

    assert body["skipped_series"] == [
        {"location_id": "loc-sim-1", "material_type": "brown", "reason": "not_enough_records"}
    ]
    assert any(
        label == "simulation based on historical rates, not a prediction of reality"
        for label in body["assumptions"]
    )


def test_default_window_and_frequency_echo(client: TestClient) -> None:
    """No request levers: simulation_days defaults to the observed window
    length (2026-01-01..2026-01-05 = 5 days) and frequency_days to the §4.6
    default 28 -> nothing is due within 5 days (max days_since 0 < 28)."""
    _upload(client)
    body = _post(client, "/api/scenarios", {})
    echo = body["config_echo"]
    assert echo["simulation_days"] == 5
    assert echo["frequency_days"] == 28
    assert all(strategy["stops_total"] == 0 for strategy in body["strategies"])
    assert all(strategy["cost_eur_total"] == 0.0 for strategy in body["strategies"])


def test_policy_threshold_override_moves_demand_driven(client: TestClient) -> None:
    """policy_config select_threshold_pct=10 -> demand_driven empties at
    fill >= 10 counting from the clock start 2026-01-01 (§5.2.5
    initialisation): 01-03 (5 pp/day x 2 d), reset; 01-05 (x 2 d), reset;
    01-07, 01-09, 01-11 likewise — 5 stops -> 5 truck-days;
    cost 5 x 500.0 = 2500.0; per-year round(2500.0 / 12 x 200, 2) = 41666.67.
    fixed_frequency is unchanged (its due rule ignores the threshold)."""
    _upload(client)
    body = _post(
        client,
        "/api/scenarios",
        {
            "frequency_days": FREQUENCY_DAYS,
            "simulation_days": SIMULATION_DAYS,
            "policy_config": {"select_threshold_pct": 10},
        },
    )
    strategies = {strategy["id"]: strategy for strategy in body["strategies"]}
    demand = strategies["demand_driven"]
    assert demand["stops_total"] == 5  # 01-03, 01-05, 01-07, 01-09, 01-11
    assert demand["truck_days"] == 5
    assert demand["cost_eur_total"] == 2500.0
    assert demand["cost_eur_per_year"] == 41666.67  # round(2500.0 / 12 x 200, 2)
    assert demand["service"]["max_fill_pct"] == 5.0  # end-of-day: due days reset to 0
    assert demand["service"]["share_emptyings_full_or_overfull_pct"] == 0.0  # 0 of 5
    assert strategies["fixed_frequency"]["stops_total"] == 3  # threshold-independent
