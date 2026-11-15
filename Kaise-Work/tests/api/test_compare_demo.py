"""Compare-demo CLI tests (M12 v2) — docs/contracts.md §4.6/§4.7/§5.2.2.

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

# Hand-computed expectations (container 1900 L, density 0.5 kg/l [demo §4.6]):
# persistence fills at as_of: CMP-1 90 -> 1710 L / 855 kg, CMP-2 80 -> 1520 L /
# 760 kg, CMP-4 20 -> 380 L / 190 kg, CMP-3 no persistence -> 0 L / 0 kg.
EXPECTED_LITRES_ALL = 1710 + 1520 + 0 + 380  # 3610 — naive_sweep_all (4 series)
EXPECTED_KG_ALL = 855 + 760 + 0 + 190  # 1805
EXPECTED_LITRES_SELECTED = 1710 + 1520  # 3230 — selected scenarios (90 + 80)
EXPECTED_KG_SELECTED = 855 + 760  # 1615

SCENARIO_ORDER = ["naive_sweep_all", "naive_sweep_selected", "ortools"]


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


def test_sweep_all_visits_all_four_series(comparison: ComparisonResult) -> None:
    sweep_all = comparison.run.scenarios[0]
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
    sweep_selected = comparison.run.scenarios[1]
    selected = comparison.run.optimised_median.selection.selected
    assert len(selected) == 2  # 90 and 80 >= threshold 80
    assert len(comparison.run.optimised_median.selection.skipped) == 2
    assert sweep_selected.stops_total == sweep_selected.stops_served == 2
    assert comparison.run.sweep_selected.no_forecast_stop_keys == []
    # Same physics, subset of the all-series sweep.
    assert sweep_selected.collected_volume_litres == EXPECTED_LITRES_SELECTED
    assert sweep_selected.collected_weight_kg == EXPECTED_KG_SELECTED


def test_ortools_row_is_the_median_run_pipeline(comparison: ComparisonResult) -> None:
    ortools_row = comparison.run.scenarios[2]
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


def test_sweep_all_collected_quantities_match_hand_check(
    comparison: ComparisonResult,
) -> None:
    sweep_all = comparison.run.scenarios[0]
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
        # Fleet recommendation covers full demand: ceil(3610/12000)=1,
        # ceil(1805/10000)=1 (demo_truck §4.6) for the all-sweep.
    assert comparison.run.scenarios[0].recommended_trucks == 1


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
    sweep_all, sweep_selected, ortools_row = comparison.run.scenarios
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
    assert "Scenario 1" in markdown and "Scenario 2" in markdown and "Scenario 3" in markdown
    assert "## Gains" in markdown
    assert "## Optimised determinism" in markdown
    assert "haversine_straight_line_derived" in markdown
    assert 'never "road distance"' in markdown  # AGENTS rule 9 / contract §4.2
    assert "[demo assumption]" in markdown
    assert "detour factor" in markdown
    assert "python -m src.api.compare_demo" in markdown
    assert "solution budget" in markdown  # DETERMINISM_NOTE (§4.4/§4.7)
    assert "0 L / 0 kg" in markdown  # zero-fill labelling
    assert "area sweep" in markdown
    assert "distance per stop served" in markdown
    assert "distance per collected kg" in markdown


def test_document_numbers_match_the_run(comparison: ComparisonResult) -> None:
    markdown = comparison.markdown
    sweep_all, sweep_selected, ortools_row = comparison.run.scenarios
    # The document is rendered from the very run under test.
    assert str(sweep_all.distance_m) in markdown
    assert str(sweep_selected.distance_m) in markdown
    assert str(ortools_row.distance_m) in markdown
    assert str(EXPECTED_LITRES_ALL) in markdown
    assert str(EXPECTED_KG_ALL) in markdown
    assert "1 x demo_truck (ceil_by_volume 1, ceil_by_weight 1)" in markdown
    assert "2 selected / 2 skipped" in markdown
    gains = comparison.run.gains
    assert str(gains.selection_gain_m) in markdown
    det = comparison.run.optimised_determinism
    assert str(det.distance_m_min) in markdown and str(det.distance_m_max) in markdown


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
