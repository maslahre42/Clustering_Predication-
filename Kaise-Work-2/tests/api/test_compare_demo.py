"""Compare-demo CLI tests (M15 v3) — docs/contracts.md §4.6/§4.7/§5.2.2.

Runs the §4.7 comparison on a small **synthetic** CSV (SYNTHETIC-prefixed
ids, hand-authored — never real data) and pins the generated document's
structure, labels and arithmetic. Everything is computed by the shared core
``services.run_comparison`` (5 optimised solves + 2 naive sweeps); the
fixture runs the CLI ``run_comparison`` once per module and asserts scenario
rows, gains, determinism and document against that single run.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src.api.compare_demo import ComparisonResult, main, run_comparison

AS_OF = date(2026, 9, 30)

CSV_ROWS = """Location_id,material_type,date,fill_level_perc
SYN-CMP-1,brown,2026-08-15,60
SYN-CMP-1,brown,2026-09-15,90
SYN-CMP-2,green,2026-08-20,40
SYN-CMP-2,green,2026-09-10,80
SYN-CMP-3,white,2026-08-25,overfull
SYN-CMP-3,white,2026-09-05,overfull
SYN-CMP-4,brown,2026-09-12,20
"""

# Hand-computed expectations (container 3000 L [representative §4.6 v3],
# density 0.40 kg/l [literature §4.6 v4 — AVV 20 01 02]; arithmetic:
# 90 % x 3000 L = 2700 L x 0.40 = 1080 kg; 80 % -> 2400 L x 0.40 = 960 kg;
# 20 % -> 600 L x 0.40 = 240 kg; CMP-3 no persistence -> 0 L / 0 kg).
# Persistence fills at as_of 2026-09-30: CMP-1 90, CMP-2 80, CMP-4 20,
# CMP-3 none.
EXPECTED_LITRES_ALL = 2700 + 2400 + 0 + 600  # 5700 — naive_sweep_all (4 series)
EXPECTED_KG_ALL = 1080 + 960 + 0 + 240  # 2280
EXPECTED_LITRES_SELECTED = 2700 + 2400  # 5100 — selected scenarios (90 + 80)
EXPECTED_KG_SELECTED = 1080 + 960  # 2040

SCENARIO_ORDER = [
    "naive_fixed_frequency",
    "naive_sweep_all",
    "naive_sweep_selected",
    "ortools",
]


@pytest.fixture(scope="module")
def comparison(tmp_path_factory: pytest.TempPathFactory) -> ComparisonResult:
    csv_path = tmp_path_factory.mktemp("data") / "synthetic_compare.csv"
    csv_path.write_text(CSV_ROWS, encoding="utf-8")
    output_path = csv_path.parent / "demo_numbers.md"
    return run_comparison(csv_path, output_path, as_of=AS_OF, horizon_days=28)


# ---------------------------------------------------------------------------
# §4.7 scenarios array — fixed order, ids
# ---------------------------------------------------------------------------


def test_scenarios_in_fixed_contract_order(comparison: ComparisonResult) -> None:
    assert [row.method for row in comparison.run.scenarios] == SCENARIO_ORDER


def test_fixed_frequency_status_quo_row(comparison: ComparisonResult) -> None:
    """§4.7 v4 status quo, hand check: as_of 2026-09-30, frequency_days 28
    (§4.6 default). Last emptying dates and gaps to as_of:
    CMP-1 2026-09-15 -> 15 d; CMP-2 2026-09-10 -> 20 d; CMP-3 2026-09-05 ->
    25 d; CMP-4 2026-09-12 -> 18 d. No gap reaches 28 d, so NO series is due:
    the scenario visits nothing (never fabricates work)."""
    row = comparison.run.scenarios[0]
    sweep = comparison.run.fixed_frequency
    assert row.method == "naive_fixed_frequency"
    assert sweep.method == "naive_fixed_frequency"
    assert row.status == "complete"  # nothing visited, nothing unserved
    assert row.stops_total == row.stops_served == 0
    assert row.unserved_count == 0
    assert row.vehicles_used == 0
    assert row.distance_m == 0
    assert row.duration_min == 0
    assert row.collected_volume_litres == 0
    assert row.collected_weight_kg == 0
    # Zero denominators ⇒ null per-stop/per-kg metrics (§5.2.2).
    assert row.distance_per_stop_m is None
    assert row.distance_per_kg_m is None
    assert row.cost_eur_per_day == 0 * 500.0
    # Fleet recommendation still covers FULL demand (§4.4), not just due stops.
    assert row.recommended_trucks >= 1


def test_observed_service_anchor(comparison: ComparisonResult) -> None:
    """§4.7 v4/§5.2.4 anchor over the fixture's 7 records (4 series):
    numeric >= 100 — none; overfull — CMP-3 white x 2 ⇒ 2/7 x 100 = 28.6 %
    (1 d.p.); max numeric fill = 90.0 (CMP-1's 2026-09-15 record)."""
    anchor = comparison.run.observed_anchor
    assert anchor.basis == "observed_emptying_records"
    assert anchor.share_full_or_overfull_pct == 28.6
    assert anchor.max_fill_pct == 90.0


def test_sweep_all_visits_all_four_series(comparison: ComparisonResult) -> None:
    sweep_all = comparison.run.scenarios[1]
    assert sweep_all.status == "complete"
    assert sweep_all.stops_total == 4
    assert sweep_all.stops_served == 4
    assert sweep_all.unserved_count == 0
    assert sweep_all.vehicles_used == 1  # all four fit one demo truck in-shift
    sweep = comparison.run.sweep_all
    assert sweep.no_forecast_stop_keys == [("SYN-CMP-3", "white")]
    assert sweep.shift_violations == []
    assert sweep.status == "complete"


def test_sweep_selected_routes_policy_selected_only(comparison: ComparisonResult) -> None:
    sweep_selected = comparison.run.scenarios[2]
    selected = comparison.run.optimised_median.selection.selected
    assert len(selected) == 2  # 90 and 80 >= threshold 80
    assert len(comparison.run.optimised_median.selection.skipped) == 2
    assert sweep_selected.stops_total == sweep_selected.stops_served == 2
    assert comparison.run.sweep_selected.no_forecast_stop_keys == []
    # Same physics, subset of the all-series sweep.
    assert sweep_selected.collected_volume_litres == EXPECTED_LITRES_SELECTED
    assert sweep_selected.collected_weight_kg == EXPECTED_KG_SELECTED


def test_ortools_row_is_the_median_run_pipeline(comparison: ComparisonResult) -> None:
    ortools_row = comparison.run.scenarios[3]
    solution = comparison.run.optimised_median.solution
    assert ortools_row.status in ("optimal", "feasible")
    assert ortools_row.status == solution.status
    assert ortools_row.stops_total == 2
    assert ortools_row.stops_served == 2
    assert ortools_row.unserved_count == 0
    assert ortools_row.collected_volume_litres == EXPECTED_LITRES_SELECTED
    assert ortools_row.collected_weight_kg == EXPECTED_KG_SELECTED
    assert solution.unserved == []
    assert solution.distance_provenance == "haversine_straight_line_derived"
    # §4.3/§5.2.2 v3: mode echo + derived cost on the scenario row.
    assert ortools_row.travel_time_mode == "fixed_per_leg"
    assert ortools_row.cost_eur_per_day == 1 * 500.0  # vehicles_used x rate
    assert ortools_row.cost_eur_per_year == 500.0 * 200


def test_sweep_all_collected_quantities_match_hand_check(
    comparison: ComparisonResult,
) -> None:
    sweep_all = comparison.run.scenarios[1]
    assert sweep_all.collected_volume_litres == EXPECTED_LITRES_ALL
    assert sweep_all.collected_weight_kg == EXPECTED_KG_ALL


def test_scenario_rows_reconcile_and_echo_demo_fleet(
    comparison: ComparisonResult,
) -> None:
    for row in comparison.run.scenarios:
        assert row.stops_served + row.unserved_count == row.stops_total
        assert row.vehicles_available == 3  # §4.6 demo_truck count
        assert row.distance_m >= 0
        assert row.duration_min >= 0
        assert set(row.fleet_basis.model_dump()) == {"ceil_by_volume", "ceil_by_weight"}
        # §5.2.2 v3: cost fields derive from the §4.6 rates on every row.
        assert row.travel_time_mode == "fixed_per_leg"
        assert row.cost_eur_per_day == row.vehicles_used * 500.0
        assert row.cost_eur_per_year == row.cost_eur_per_day * 200
        # Fleet recommendation covers full demand: ceil(5700/12000)=1,
        # ceil(2280/10000)=1 (demo_truck §4.6) for the all-sweep.
    assert comparison.run.scenarios[1].recommended_trucks == 1
    # §5.2.2 fleet_budget: the ortools recommendation priced at the same rates.
    budget = comparison.run.fleet_budget
    ortools_row = comparison.run.scenarios[3]
    assert budget.vehicle_type_id == "demo_truck"
    assert budget.trucks == ortools_row.recommended_trucks
    assert budget.cost_eur_per_day == budget.trucks * 500.0
    assert budget.cost_eur_per_year == budget.cost_eur_per_day * 200


def test_per_stop_and_per_kg_metrics_match_rows(comparison: ComparisonResult) -> None:
    for row in comparison.run.scenarios:
        if row.stops_served > 0:
            assert row.distance_per_stop_m == round(row.distance_m / row.stops_served, 1)
        else:
            assert row.distance_per_stop_m is None  # never a fabricated 0-division
        if row.collected_weight_kg > 0:
            assert row.distance_per_kg_m == round(row.distance_m / row.collected_weight_kg, 1)
        else:
            assert row.distance_per_kg_m is None


def test_distance_provenance_labelled_everywhere(comparison: ComparisonResult) -> None:
    assert comparison.run.distance_provenance == "haversine_straight_line_derived"
    assert comparison.run.sweep_all.distance_provenance == "haversine_straight_line_derived"
    assert comparison.run.sweep_selected.distance_provenance == "haversine_straight_line_derived"


# ---------------------------------------------------------------------------
# §4.7 gains and determinism
# ---------------------------------------------------------------------------


def test_gains_match_scenario_distances(comparison: ComparisonResult) -> None:
    sweep_all, sweep_selected, ortools_row = comparison.run.scenarios[1:]
    gains = comparison.run.gains
    assert gains.selection_gain_m == sweep_all.distance_m - sweep_selected.distance_m
    # The optimised scenario solved to a usable status here, so the routing
    # gain against its median distance must be present (never fabricated).
    assert ortools_row.status in ("optimal", "feasible")
    assert gains.routing_gain_m == sweep_selected.distance_m - ortools_row.distance_m
    assert gains.total_gain_m == gains.selection_gain_m + gains.routing_gain_m


def test_determinism_section_reports_the_repetition_protocol(
    comparison: ComparisonResult,
) -> None:
    det = comparison.run.optimised_determinism
    assert det.runs == 5  # §4.7 [demo assumption]
    assert det.distance_m_min <= det.distance_m_median <= det.distance_m_max
    if det.mode == "identical":
        assert det.distance_m_min == det.distance_m_max
        assert det.distance_m_median == float(det.distance_m_min)
    else:
        assert det.distance_m_min < det.distance_m_max


# ---------------------------------------------------------------------------
# Generated document — structure, labels, arithmetic
# ---------------------------------------------------------------------------


def test_document_labels_and_structure(comparison: ComparisonResult) -> None:
    markdown = comparison.markdown
    assert "# Demo numbers" in markdown
    for method in SCENARIO_ORDER:
        assert method in markdown
    assert (
        "Scenario 1" in markdown
        and "Scenario 2" in markdown
        and "Scenario 3" in markdown
        and "Scenario 4" in markdown
    )
    assert "## Gains" in markdown
    assert "## Optimised determinism" in markdown
    assert "## Fleet budget" in markdown  # §5.2.2 v3 fleet-budget section
    assert "Observed service anchor" in markdown  # §4.7 v4 status-quo service
    assert "haversine_straight_line_derived" in markdown
    assert 'never "road distance"' in markdown  # AGENTS rule 9 / contract §4.2
    assert "[demo assumption]" in markdown
    assert "[representative]" in markdown  # §4.6 v3 per-value sources
    assert "[literature]" in markdown  # §4.6 v4 density source
    assert "v3 parameter change" in markdown  # supersession note
    assert "detour factor" in markdown
    assert "python -m src.api.compare_demo" in markdown
    assert "solution budget" in markdown  # DETERMINISM_NOTE (§4.4/§4.7)
    assert "0 L / 0 kg" in markdown  # zero-fill labelling
    assert "area sweep" in markdown
    assert "distance per stop served" in markdown
    assert "distance per collected kg" in markdown
    assert "travel_time_mode" in markdown  # v3 mode echo per scenario
    assert "cost EUR/day" in markdown and "cost EUR/year" in markdown


def test_document_numbers_match_the_run(comparison: ComparisonResult) -> None:
    markdown = comparison.markdown
    sweep_all, sweep_selected, ortools_row = comparison.run.scenarios[1:]
    # The document is rendered from the very run under test.
    assert str(sweep_all.distance_m) in markdown
    assert str(sweep_selected.distance_m) in markdown
    assert str(ortools_row.distance_m) in markdown
    assert str(EXPECTED_LITRES_ALL) in markdown
    assert str(EXPECTED_KG_ALL) in markdown
    assert "1 x demo_truck (ceil_by_volume 1, ceil_by_weight 1)" in markdown
    assert "2 selected / 2 skipped" in markdown
    # §4.7 v4 observed anchor line (§5.2.4 arithmetic, n_rows denominator):
    # 2 of 7 records (n_rows) full or overfull = 28.6 %; max numeric fill 90
    # (CMP-1's last record).
    assert "28.6 % of emptying records full or overfull" in markdown
    assert "max observed numeric fill: 90.0 %" in markdown
    gains = comparison.run.gains
    assert str(gains.selection_gain_m) in markdown
    det = comparison.run.optimised_determinism
    assert str(det.distance_m_min) in markdown and str(det.distance_m_max) in markdown
    # Fleet-budget line: money with thousands separators, no scientific
    # notation (renderer _eur), trucks = the ortools recommendation.
    budget = comparison.run.fleet_budget
    assert f"fleet_budget: {budget.trucks} x {budget.vehicle_type_id}" in markdown
    assert f"{budget.cost_eur_per_day:,.0f} EUR/day" in markdown
    assert f"{budget.cost_eur_per_year:,.0f} EUR/year" in markdown


def test_determinism_mode_wording_matches(comparison: ComparisonResult) -> None:
    markdown = comparison.markdown
    det = comparison.run.optimised_determinism
    if det.mode == "identical":
        assert "identical (min == max" in markdown
    else:
        assert "median_of_runs (wall-clock variance observed" in markdown


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def test_main_exit_zero_writes_document(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    csv_path = tmp_path_factory.mktemp("cli") / "synthetic_compare.csv"
    csv_path.write_text(CSV_ROWS, encoding="utf-8")
    output_path = csv_path.parent / "nested" / "demo_numbers.md"
    exit_code = main(
        [
            "--data",
            str(csv_path),
            "--output",
            str(output_path),
            "--as-of",
            AS_OF.isoformat(),
            "--horizon",
            "28",
        ]
    )
    assert exit_code == 0
    assert output_path.exists()
    document = output_path.read_text(encoding="utf-8")
    assert "Scenario 1" in document
    assert SCENARIO_ORDER[2] in document


def test_main_malformed_as_of_exits_two(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    csv_path = tmp_path_factory.mktemp("cli-bad") / "synthetic_compare.csv"
    csv_path.write_text(CSV_ROWS, encoding="utf-8")
    output_path = csv_path.parent / "demo_numbers.md"
    exit_code = main(
        ["--data", str(csv_path), "--output", str(output_path), "--as-of", "30-09-2026"]
    )
    assert exit_code == 2
    assert not output_path.exists()  # clean failure, no traceback, no partial doc
