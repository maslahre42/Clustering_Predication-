"""M12 demo comparison CLI — §4.7 gain-decomposition scenarios (v2).

Runs the agreed §4.6 demo pipeline on the challenge dataset and writes
``docs/demo_numbers.md``:

    python -m src.api.compare_demo

Lives in the API layer (AGENTS boundaries): everything is computed by the ONE
shared core ``src.api.services.run_comparison`` — the same function behind
GET /api/comparison (§5.2.2) — reusing the M10 ``run_route`` pipeline exactly
(persistence forecast §2.3, as_of 2026-09-30, horizon_days 28 [demo
assumption], default ``PolicyConfig`` §3.1, synthetic demo geography §4.5 and
§4.6 demo config, solved ``runs`` times by ``src.routing.solver.solve``) plus
the two naive area-sweep scenarios from ``src.routing.naive``. This module is
CLI glue only: upload, the markdown rendering below, and argparse.

The three §4.7 scenarios, in the fixed array order:
- ``naive_sweep_all``: ALL dataset series — no policy filter — simulated by
  ``src.routing.naive`` in the §4.7 area-sweep order (grid cells of
  ``SWEEP_CELL_SIZE_DEG`` ≈ 1 km [demo assumption], row-major, lexicographic
  within a cell) [demo assumption — the data has no area field]. Series
  without a persistence value at as_of (§2.3) are still visited and collect
  0 L / 0 kg, labelled.
- ``naive_sweep_selected``: the same sweep over policy-selected series only
  (gain reference).
- ``ortools``: the §4.7 median of ``runs`` optimised solves (selection counts
  from that median run's policy selection).

Every number in the generated document is labelled observed / predicted /
[demo assumption]; distances are haversine_straight_line_derived (detour
factor applied) and are **never** called road distance (contract §4.2, AGENTS
rule 9). Per-stop/per-kg metrics are null on zero denominators — never a
fabricated 0-division value (§5.2.2).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from src.api import schemas as api_schemas
from src.api.services import (
    COMPARISON_AS_OF_DEFAULT,
    COMPARISON_HORIZON_DAYS_DEFAULT,
    DEMO_CSV_PATH,
    DETERMINISM_NOTE,
    ComparisonRun,
    upload_dataset,
)
from src.api.services import run_comparison as run_comparison_core
from src.routing.demo_config import demo_vehicle_type
from src.routing.naive import SWEEP_CELL_SIZE_DEG, NaiveSolution

# CLI-facing names for the single server-side/API shared constants (§5.1/§5.2.2);
# kept as module attributes so argparse defaults and external references
# (``compare_demo.DEFAULT_CSV_PATH`` etc.) stay stable.
DEFAULT_CSV_PATH = DEMO_CSV_PATH
DEFAULT_OUTPUT_PATH = Path("docs/demo_numbers.md")
DEFAULT_AS_OF = COMPARISON_AS_OF_DEFAULT
DEFAULT_HORIZON_DAYS = COMPARISON_HORIZON_DAYS_DEFAULT  # [demo assumption]

DETOUR_NOTE = (
    'great-circle haversine x detour factor (§4.6) [demo assumption]; never "road '
    'distance" — no road network data exists [observed]'
)

SCENARIO_HEADINGS: dict[str, str] = {
    "naive_sweep_all": (
        "Scenario 1 — naive_sweep_all (ALL series, no policy filter, naive area-sweep order)"
    ),
    "naive_sweep_selected": (
        "Scenario 2 — naive_sweep_selected (policy-selected series only, same area-sweep order)"
    ),
    "ortools": "Scenario 3 — ortools (OR-Tools CVRP, `src.routing.solver.solve`)",
}


class CompareDemoError(RuntimeError):
    """Raised when the comparison inputs are unusable (dataset validation
    errors) — the CLI reports the full error list and exits non-zero."""


@dataclass(frozen=True)
class ComparisonResult:
    """The §4.7 comparison run plus the rendered markdown document."""

    csv_path: Path
    output_path: Path
    as_of: date
    horizon_days: int
    n_rows: int
    n_locations: int
    n_series: int
    date_min: date | None
    date_max: date | None
    run: ComparisonRun
    markdown: str


def run_comparison(
    csv_path: Path,
    output_path: Path,
    as_of: date = DEFAULT_AS_OF,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
) -> ComparisonResult:
    """Run the §4.7 comparison on ``csv_path`` and render the markdown document.

    Everything is computed by the shared core ``services.run_comparison``
    (also powering GET /api/comparison, §5.2.2): the optimised scenario
    reuses the M10 pipeline untouched (upload → ``run_route`` on the active
    store dataset, ``runs`` solves, median run); the two naive scenarios
    share the same demo config values and coordinate derivation (§4.7).
    """
    load_result = upload_dataset(csv_path.read_bytes(), csv_path.name)
    if load_result.errors:
        raise CompareDemoError(
            "dataset failed §1 validation with "
            f"{len(load_result.errors)} error(s); first: {load_result.errors[0]!r}"
        )
    summary = load_result.dataset.summary

    run = run_comparison_core(load_result.dataset, as_of, horizon_days)

    markdown = _render_markdown(
        csv_path=csv_path,
        output_path=output_path,
        as_of=as_of,
        horizon_days=horizon_days,
        n_rows=summary.n_rows,
        n_locations=summary.n_locations,
        n_series=summary.n_series,
        date_min=summary.date_min,
        date_max=summary.date_max,
        run=run,
    )
    return ComparisonResult(
        csv_path=csv_path,
        output_path=output_path,
        as_of=as_of,
        horizon_days=horizon_days,
        n_rows=summary.n_rows,
        n_locations=summary.n_locations,
        n_series=summary.n_series,
        date_min=summary.date_min,
        date_max=summary.date_max,
        run=run,
        markdown=markdown,
    )


def _ratio(value: float | None) -> str:
    """Null-aware per-stop/per-kg cell (§5.2.2: never a fabricated value)."""
    if value is None:
        return "null (zero denominator — not fabricated, §5.2.2)"
    return str(value)


def _median_number(value: float) -> str:
    """Render the determinism median without a spurious ``.0`` (the value is
    the median of integer distances; a half-integer stays explicit)."""
    return str(int(value)) if value == int(value) else str(value)


def _scenario_table(row: api_schemas.ComparisonScenarioResponse) -> list[str]:
    """The §4.7-key metric rows for one scenario, from the shared core row."""
    vehicle = demo_vehicle_type()  # id from the §4.6 config, never literals
    return [
        "| metric | value |",
        "|---|---|",
        f"| status | {row.status} |",
        f"| total distance_m | {row.distance_m} (haversine_straight_line_derived) |",
        f"| total duration_min | {row.duration_min} |",
        f"| stops visited | {row.stops_served} / {row.stops_total} |",
        f"| vehicles available | {row.vehicles_available} x {vehicle.id} [demo assumption §4.6] |",
        f"| vehicles used | {row.vehicles_used} |",
        f"| collected volume litres | {row.collected_volume_litres} |",
        f"| collected weight kg | {row.collected_weight_kg} |",
        f"| unserved stops | {row.unserved_count} (each with a reason in the solution) |",
        f"| fleet recommendation | {row.recommended_trucks} x {vehicle.id} "
        f"(ceil_by_volume {row.fleet_basis.ceil_by_volume}, "
        f"ceil_by_weight {row.fleet_basis.ceil_by_weight}) |",
        f"| distance per stop served (m) | {_ratio(row.distance_per_stop_m)} |",
        f"| distance per collected kg (m) | {_ratio(row.distance_per_kg_m)} |",
    ]


def _sweep_lines(sweep: NaiveSolution, row: api_schemas.ComparisonScenarioResponse) -> list[str]:
    """Zero-fill and shift labelling for one naive sweep (contract §2.3/§4.4)."""
    return [
        "",
        f"Stops with no persistence value at as_of: {len(sweep.no_forecast_stop_keys)} of "
        f"{row.stops_total} — still visited, collect 0 L / 0 kg [demo assumption "
        "labelling; contract §2.3: no number is fabricated].",
        "",
        f"Shift overruns reported (contract §4.4): {len(sweep.shift_violations)}",
    ]


def _gains_lines(run: ComparisonRun) -> list[str]:
    """§4.7 gain decomposition; null-aware when the optimised scenario has no
    usable solution (infeasible/timeout — a gain against 0 would be
    fabricated, §5.2.2)."""
    gains = run.gains
    optimised_status = run.optimised_median.solution.status
    routing_text = (
        str(gains.routing_gain_m)
        if gains.routing_gain_m is not None
        else f"null — the optimised scenario has status {optimised_status}; a gain "
        "against 0 would be fabricated (§5.2.2)"
    )
    total_text = str(gains.total_gain_m) if gains.total_gain_m is not None else "null"
    return [
        f"- selection_gain_m (naive_sweep_all - naive_sweep_selected): {gains.selection_gain_m}",
        f"- routing_gain_m (naive_sweep_selected - ortools median): {routing_text}",
        f"- total_gain_m: {total_text}",
        "",
        "Different served-stop counts across scenarios are inherent — normalise "
        "with the per-stop/per-kg metrics in the tables above; never claim "
        "like-for-like distance (§4.7).",
    ]


def _determinism_lines(run: ComparisonRun) -> list[str]:
    """§4.7 repetition protocol section, from ``optimised_determinism``."""
    det = run.optimised_determinism
    mode_text = (
        "identical (min == max — deterministic solution-budget stop, §4.4)"
        if det.mode == "identical"
        else "median_of_runs (wall-clock variance observed — the median is the "
        "value used in this document; reported, never hidden)"
    )
    return [
        f"- runs: {det.runs}",
        f"- mode: {mode_text}",
        f"- distance_m min / median / max: {det.distance_m_min} / "
        f"{_median_number(det.distance_m_median)} / {det.distance_m_max}",
    ]


def _render_markdown(
    csv_path: Path,
    output_path: Path,
    as_of: date,
    horizon_days: int,
    n_rows: int,
    n_locations: int,
    n_series: int,
    date_min: date | None,
    date_max: date | None,
    run: ComparisonRun,
) -> str:
    """Render the three §4.7 scenarios, gains, determinism and labels."""
    sweeps = {
        "naive_sweep_all": run.sweep_all,
        "naive_sweep_selected": run.sweep_selected,
    }
    lines: list[str] = []
    add = lines.append

    add("# Demo numbers — naive sweep vs optimised comparison (M12 v2)")
    add("")
    add(
        f"Reproducing command: `python -m src.api.compare_demo` (writes `{output_path}`; "
        "optional overrides `--data PATH --output PATH --as-of YYYY-MM-DD --horizon N`)"
    )
    add("")
    add(
        f"Dataset: `{csv_path}` [observed] — {n_rows} rows, {n_locations} locations, "
        f"{n_series} series, {date_min}..{date_max}. Raw file immutable (AGENTS rule 4)."
    )
    add("")
    add(
        f"Prediction: as_of {as_of}, horizon_days {horizon_days} [demo assumption — the "
        "brief defines no horizon; the default is the observed median reading gap], "
        "method persistence (contract §2.3)."
    )
    add("")
    add(
        f"Distance provenance for ALL scenarios: haversine_straight_line_derived — "
        f"{DETOUR_NOTE}. Synthetic stop coordinates derive from SHA-256 of series keys; "
        "the depot and disposal site are synthetic fixtures near Heilbronn."
    )
    add("")
    add(
        f"Naive visiting order (both sweep scenarios): §4.7 area sweep — grid cells of "
        f"SWEEP_CELL_SIZE_DEG={SWEEP_CELL_SIZE_DEG}° (~1 km [demo assumption]), "
        "row-major (lat band ascending, then lon ascending), lexicographic "
        "(location_id, material_type) within a cell [demo assumption — the data has "
        "no area field, so the order is not geographic]."
    )
    add("")
    for scenario in run.scenarios:
        add(f"## {SCENARIO_HEADINGS[scenario.method]}")
        add("")
        lines.extend(_scenario_table(scenario))
        sweep = sweeps.get(scenario.method)
        if sweep is not None:
            lines.extend(_sweep_lines(sweep, scenario))
        add("")
    selection = run.optimised_median.selection
    add(
        f"Selection (policy §3, default config): {len(selection.selected)} selected / "
        f"{len(selection.skipped)} skipped — the ortools and naive_sweep_selected "
        "scenarios route only selected candidates; naive_sweep_all visits all "
        f"{run.sweep_all.totals.stops_total} series."
    )
    add("")
    add("## Gains (derived, metres — contract §4.7)")
    add("")
    lines.extend(_gains_lines(run))
    add("")
    add(
        f"## Optimised determinism (§4.7 repetition protocol, "
        f"{run.optimised_determinism.runs} solves)"
    )
    add("")
    lines.extend(_determinism_lines(run))
    add("")
    add("## Assumptions (each labelled [demo assumption])")
    add("")
    for assumption in run.assumptions:
        add(f"- {assumption}")
    add("")
    add("## Notes")
    add("")
    add(f"- {DETERMINISM_NOTE}")
    add(
        "- Unserved stops are never silently dropped (contract §4.4); the generated "
        "solution objects carry a deterministic reason per stop."
    )
    add("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point: run the §4.7 comparison and write the markdown doc."""
    parser = argparse.ArgumentParser(
        description=(
            "M12 demo comparison: naive area sweeps vs OR-Tools optimised "
            "(§4.7 scenarios, gains, determinism)."
        )
    )
    parser.add_argument("--data", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--as-of", default=DEFAULT_AS_OF.isoformat())
    parser.add_argument("--horizon", type=int, default=DEFAULT_HORIZON_DAYS)
    arguments = parser.parse_args(argv)
    try:
        as_of = datetime.strptime(arguments.as_of, "%Y-%m-%d").date()
        result = run_comparison(
            arguments.data, arguments.output, as_of=as_of, horizon_days=arguments.horizon
        )
    except (OSError, ValueError, CompareDemoError) as error:
        # ValueError covers a malformed --as-of (strptime) and any downstream
        # validation error — reported cleanly on stderr, never a traceback.
        print(f"compare_demo failed: {error}", file=sys.stderr)
        return 2
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(result.markdown, encoding="utf-8")
    scenario_counts = ", ".join(
        f"{scenario.method} {scenario.stops_served}/{scenario.stops_total}"
        for scenario in result.run.scenarios
    )
    print(
        f"wrote {arguments.output} ({scenario_counts} served; "
        f"optimised determinism mode={result.run.optimised_determinism.mode})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
