import { afterEach, describe, expect, it, vi } from "vitest";
import { RoutePanel } from "./RoutePanel";
import type { RouteResponse } from "../lib/api";
import { click, cleanup, jsonResponse, render } from "../test/dom";
import { routeResponseFixture } from "../test/fixtures";
import realRouteCapture from "../test/fixtures/real-capture/route.json";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("RoutePanel", () => {
  it("renders solver status, totals with units, fleet recommendation and unserved reasons", async () => {
    const fetchMock = vi.fn(
      async (_url: RequestInfo | URL, _init?: RequestInit): Promise<Response> =>
        jsonResponse(routeResponseFixture),
    );
    vi.stubGlobal("fetch", fetchMock);
    const onRoute = vi.fn();

    render(
      <RoutePanel
        defaultAsOf="2026-10-31"
        policyOverride={{}}
        routingOverride={{}}
        onRoute={onRoute}
      />,
    );
    await click(document.querySelector('[data-testid="route-run"]'));

    const [url] = fetchMock.mock.calls[0] as [RequestInfo | URL];
    expect(String(url)).toBe("/api/route");

    expect(document.querySelector('[data-testid="solve-status"]')?.textContent).toContain(
      "feasible",
    );
    const totals = document.querySelector('[data-testid="route-totals"]')?.textContent ?? "";
    expect(totals).toContain("18,400 m (18.4 km)");
    expect(totals).toContain("95 min");
    expect(totals).toContain("1,200 L");
    expect(totals).toContain("600 kg");
    expect(totals).toContain("2 of 3");
    expect(totals).toContain("1 vehicle(s)");
    expect(totals).toContain("by volume");

    const unserved = document.querySelector('[data-testid="unserved-list"]')?.textContent ?? "";
    expect(unserved).toContain("11111111-2222-3333-4444-555555555555 · white");
    expect(unserved).toContain("max_shift_minutes");

    // Load progression + straight-line provenance never pass as road distance.
    expect(document.body.textContent).toContain("1,200 L / 600 kg");
    expect(document.body.textContent).toContain("NOT road distance");

    // Assumptions surfaced to the parent for the synthetic-data banner (§5.3).
    expect(onRoute).toHaveBeenCalledWith(routeResponseFixture);
    expect((onRoute.mock.calls[0]?.[0] as RouteResponse).assumptions.length).toBe(2);
  });

  /**
   * Regression (review 2026-11-14): renders the VERBATIM real backend route
   * response (POST /api/route, real CSV upload, as_of 2026-09-30). Real wire
   * shapes: FLAT unserved {location_id, material_type, reason} (no stop_key)
   * and load_progression as [volume, weight] TUPLE arrays. The old mocked
   * fixtures used the wrong shapes and masked these crash bugs.
   */
  it("renders the real captured route: 415 unserved with reasons, tuple load progression", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(realRouteCapture)));
    const onRoute = vi.fn();

    render(
      <RoutePanel
        defaultAsOf="2026-09-30"
        policyOverride={{}}
        routingOverride={{}}
        onRoute={onRoute}
      />,
    );
    await click(document.querySelector('[data-testid="route-run"]'));

    expect(document.querySelector('[data-testid="solve-status"]')?.textContent).toContain(
      "feasible",
    );
    const totals = document.querySelector('[data-testid="route-totals"]')?.textContent ?? "";
    expect(totals).toContain("69,889 m (69.9 km)");
    expect(totals).toContain("601 min");
    expect(totals).toContain("47,880 L");
    expect(totals).toContain("23,940 kg");
    expect(totals).toContain("43 of 458");
    expect(totals).toContain("demo_truck");
    expect(totals).toContain("63 vehicle(s)");

    // Flat unserved entries render location · material + reason (415 of them).
    const unserved = document.querySelector('[data-testid="unserved-list"]')?.textContent ?? "";
    expect(unserved).toContain("0058ed93-88f5-4c25-8746-2e5ee87e5559 · white");
    expect(unserved).toContain("no feasible insertion");
    const unservedItems = document.querySelectorAll('[data-testid="unserved-list"] li');
    expect(unservedItems.length).toBe(415);

    // Tuple load progression renders with units: "1,900 L / 950 kg".
    expect(document.body.textContent).toContain("1,900 L / 950 kg");
    expect(onRoute).toHaveBeenCalledWith(realRouteCapture);
    expect((onRoute.mock.calls[0]?.[0] as RouteResponse).solution.unserved.length).toBe(415);
  });

  it("warns (but does not hide) when the solver returns infeasible", async () => {
    const degraded: RouteResponse = {
      ...routeResponseFixture,
      solution: {
        ...routeResponseFixture.solution,
        status: "infeasible",
        routes: [],
        totals: { ...routeResponseFixture.solution.totals, stops_served: 0 },
      },
    };
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(degraded)));

    render(
      <RoutePanel
        defaultAsOf="2026-10-31"
        policyOverride={{}}
        routingOverride={{}}
        onRoute={vi.fn()}
      />,
    );
    await click(document.querySelector('[data-testid="route-run"]'));

    expect(document.querySelector('[data-testid="degraded-status"]')?.textContent).toContain(
      "infeasible",
    );
    expect(document.querySelector('[data-testid="unserved-list"]')?.textContent).toContain(
      "max_shift_minutes",
    );
  });
});
