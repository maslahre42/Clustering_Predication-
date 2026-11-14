import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  detailMessage,
  fetchComparison,
  fetchConfig,
  fetchSummary,
  loadDemoDataset,
  runCandidates,
  runRoute,
  uploadDataset,
} from "./api";
import { jsonResponse } from "../test/dom";
import {
  comparisonFixture,
  routeResponseFixture,
  selectionFixture,
  summaryFixture,
} from "../test/fixtures";
import realUploadCapture from "../test/fixtures/real-capture/upload.json";

afterEach(() => {
  vi.unstubAllGlobals();
});

type FetchArgs = [url: RequestInfo | URL, init?: RequestInit];

function stubJsonFetch(reply: (...args: FetchArgs) => Response) {
  const fetchMock = vi.fn(async (...args: FetchArgs): Promise<Response> => reply(...args));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("api client (§5)", () => {
  it("fetchSummary GETs /api/summary and parses the DatasetSummary shape", async () => {
    const fetchMock = stubJsonFetch(() => jsonResponse(summaryFixture));

    const summary = await fetchSummary();

    expect(summary.n_rows).toBe(11701);
    expect(summary.rows_per_material.brown).toBe(3901);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/summary");
  });

  it("maps non-OK responses to ApiError carrying the status", async () => {
    stubJsonFetch(() => jsonResponse({ detail: "no dataset" }, 404));

    const error = await fetchSummary().catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(404);
    expect((error as ApiError).message).toContain("404");
  });

  it("uploadDataset POSTs multipart /api/datasets with the file and parses the flat capture shape", async () => {
    const fetchMock = stubJsonFetch(() => jsonResponse(realUploadCapture));

    const file = new File(["location_id,material_type,date,fill_level"], "glass.csv", {
      type: "text/csv",
    });
    const response = await uploadDataset(file);

    const [url, init] = fetchMock.mock.calls[0] as FetchArgs;
    expect(url).toBe("/api/datasets");
    expect(init?.method).toBe("POST");
    expect(init?.body).toBeInstanceOf(FormData);
    // Flat §5.1 shape (real capture 2026-11-14): summary fields at top level,
    // no nested `summary` key — the blank-page regression pinned here.
    expect("summary" in response).toBe(false);
    expect(response.n_rows).toBe(11701);
    expect(response.source_name).toBe("glass_fill_levels_anonymized_f.csv");
    expect(response.errors).toEqual([]);
    expect(response.warnings).toEqual([]);
  });

  it("runCandidates POSTs JSON with policy_config override", async () => {
    const fetchMock = stubJsonFetch(() => jsonResponse(selectionFixture));

    const response = await runCandidates({
      as_of_date: "2026-10-31",
      horizon_days: 28,
      method: "persistence",
      policy_config: { select_threshold_pct: 90 },
    });

    const [url, init] = fetchMock.mock.calls[0] as FetchArgs;
    expect(url).toBe("/api/candidates");
    expect(JSON.parse(init?.body as string)).toEqual({
      as_of_date: "2026-10-31",
      horizon_days: 28,
      method: "persistence",
      policy_config: { select_threshold_pct: 90 },
    });
    expect(response.config.select_threshold_pct).toBe(80);
    expect(response.selected).toHaveLength(2);
  });

  it("runRoute POSTs /api/route with snake_case routing overrides and parses §4.3 solution", async () => {
    const fetchMock = stubJsonFetch(() => jsonResponse(routeResponseFixture));

    const response = await runRoute({
      as_of_date: "2026-10-31",
      horizon_days: 28,
      method: "persistence",
      policy_config: {},
      routing_config: {
        vehicle_count_available: 2,
        densities_kg_per_litre: { brown: 0.6 },
      },
    });

    const [url, init] = fetchMock.mock.calls[0] as FetchArgs;
    expect(url).toBe("/api/route");
    const body = JSON.parse(init?.body as string) as {
      routing_config: Record<string, unknown>;
    };
    expect(body.routing_config).toEqual({
      vehicle_count_available: 2,
      densities_kg_per_litre: { brown: 0.6 },
    });
    expect(response.solution.status).toBe("feasible");
    expect(response.solution.totals.stops_served).toBe(2);
    expect(response.solution.unserved[0]?.reason).toContain("shift");
    expect(response.assumptions.length).toBeGreaterThan(0);
  });

  it("fetchConfig GETs /api/config", async () => {
    const fetchMock = stubJsonFetch(() =>
      jsonResponse({
        policy: { select_threshold_pct: 80, uncertainty_buffer_pct: 0, overfull_always_selected: true },
        routing: { container_volume_litres: 1900 },
        assumption_fields: ["container_volume_litres"],
      }),
    );

    const config = await fetchConfig();

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/config");
    expect(config.routing.container_volume_litres).toBe(1900);
  });

  it("fetchComparison GETs /api/comparison and parses the §5.2.2 v2 payload", async () => {
    const fetchMock = stubJsonFetch(() => jsonResponse(comparisonFixture));

    const comparison = await fetchComparison();

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/comparison");
    // Fixed §4.7 scenario order.
    expect(comparison.scenarios.map((s) => s.method)).toEqual([
      "naive_sweep_all",
      "naive_sweep_selected",
      "ortools",
    ]);
    expect(comparison.scenarios[0]?.distance_m).toBe(230865);
    expect(comparison.scenarios[2]?.distance_m).toBe(57657);
    // Nullable per-metrics are preserved, never coerced.
    expect(comparison.scenarios[2]?.distance_per_kg_m).toBe(2.4);
    // Gains, incl. the honestly-negative selection gain.
    expect(comparison.gains.selection_gain_m).toBe(-32130);
    expect(comparison.gains.total_gain_m).toBe(173208);
    expect(comparison.optimised_determinism).toEqual({
      runs: 5,
      mode: "identical",
      distance_m_median: 57657.0,
      distance_m_min: 57657,
      distance_m_max: 57657,
    });
    expect(comparison.distance_provenance).toBe("haversine_straight_line_derived");
  });

  it("fetchComparison preserves null per-metrics and null gains (never fabricated 0s)", async () => {
    stubJsonFetch(() =>
      jsonResponse({
        ...comparisonFixture,
        scenarios: comparisonFixture.scenarios.map((s) => ({
          ...s,
          distance_per_stop_m: null,
          distance_per_kg_m: null,
        })),
        gains: { selection_gain_m: null, routing_gain_m: null, total_gain_m: null },
      }),
    );

    const comparison = await fetchComparison();

    expect(comparison.scenarios.every((s) => s.distance_per_stop_m === null && s.distance_per_kg_m === null)).toBe(
      true,
    );
    expect(comparison.gains.selection_gain_m).toBeNull();
    expect(comparison.gains.routing_gain_m).toBeNull();
    expect(comparison.gains.total_gain_m).toBeNull();
  });

  it("fetchComparison maps 404 (no dataset loaded, §5.3) to ApiError carrying 404", async () => {
    stubJsonFetch(() => jsonResponse({ detail: "no dataset" }, 404));

    const error = await fetchComparison().catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(404);
  });

  it("loadDemoDataset POSTs /api/datasets/demo without a request body", async () => {
    const fetchMock = stubJsonFetch(() => jsonResponse(realUploadCapture));

    const response = await loadDemoDataset();

    const [url, init] = fetchMock.mock.calls[0] as FetchArgs;
    expect(url).toBe("/api/datasets/demo");
    expect(init?.method).toBe("POST");
    expect(init?.body).toBeUndefined();
    expect(response.n_rows).toBe(11701);
    expect(response.errors).toEqual([]);
  });

  it("detailMessage flattens FastAPI 422 detail arrays and strings", () => {
    expect(
      detailMessage([{ loc: ["body", "policy_config"], msg: "Input should be less than 101", type: "value_error" }]),
    ).toContain("Input should be less than 101");
    expect(detailMessage("threshold out of range")).toBe("threshold out of range");
    expect(detailMessage(undefined)).toBe("");
  });
});
