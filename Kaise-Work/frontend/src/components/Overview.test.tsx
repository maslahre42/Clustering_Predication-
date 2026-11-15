/**
 * Overview page tests (jury-usability pass): EN/DE strings, loading/empty/
 * error states, defensive guards against malformed payloads (App.test mocks
 * return {status:"ok"} for every URL — nothing may crash), the auto-candidates
 * POST body (horizon 7, as_of = date_max) and the derived-savings label rule.
 *
 * Wording discipline (docs/contracts.md §5.2.2): the data has no collection
 * events, so "emptyings" (EN) / "Leerungen" (DE) must never appear — historical
 * shares are shares of *readings*.
 */
import { afterEach, describe, expect, it, vi, type Mock } from "vitest";
import { Overview } from "./Overview";
import type { DatasetSummary } from "../lib/api";
import { cleanup, flush, jsonResponse, render } from "../test/dom";
import {
  comparisonFixture,
  comparisonMedianOfRunsFixture,
  selectionFixture,
  summaryFixture,
  summaryWithFillStats,
} from "../test/fixtures";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

type FetchArgs = [input: RequestInfo | URL, init?: RequestInit];

/** Stub fetch, routing by "METHOD path"; records every call for assertions. */
function stubRoutes(routes: Record<string, (args: FetchArgs) => Response>): Mock {
  const fetchMock = vi.fn(async (...args: FetchArgs) => {
    const [rawInput, init] = args;
    const key = `${init?.method ?? "GET"} ${String(rawInput)}`;
    const handler = routes[key];
    if (handler === undefined) {
      throw new Error(`unexpected fetch ${key}`);
    }
    return handler(args);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const happyRoutes = (): Record<string, (args: FetchArgs) => Response> => ({
  "POST /api/candidates": () => jsonResponse(selectionFixture),
  "GET /api/comparison": () => jsonResponse(comparisonFixture),
});

const emptySummary: DatasetSummary | null = null;

describe("Overview — wording discipline", () => {
  it("renders EN strings and never shows the word 'emptyings' (readings, not collection events)", async () => {
    stubRoutes(happyRoutes());
    render(
      <Overview
        lang="en"
        summary={summaryWithFillStats}
        summaryLoading={false}
        summaryError={null}
        datasetVersion={0}
        onDemoLoaded={() => {}}
      />,
    );
    await flush();
    await flush();

    const text = document.body.textContent ?? "";
    expect(text).toContain("Know which glass containers need emptying");
    expect(text).toContain("Today's recommendation");
    expect(text).toContain("Readings with full containers");
    expect(text).toContain("10.2 %");
    // Threshold note interpolated from fill_stats, not hardcoded.
    expect(text).toContain("at or above 80 % fill");
    expect(text).not.toContain("emptyings");
  });

  it("renders DE strings and never shows the word 'Leerungen'", async () => {
    stubRoutes(happyRoutes());
    render(
      <Overview
        lang="de"
        summary={summaryWithFillStats}
        summaryLoading={false}
        summaryError={null}
        datasetVersion={0}
        onDemoLoaded={() => {}}
      />,
    );
    await flush();
    await flush();

    const text = document.body.textContent ?? "";
    expect(text).toContain("Wissen, welche Glasbehälter geleert werden müssen");
    expect(text).toContain("Empfehlung für heute");
    expect(text).toContain("Messungen mit vollem Behälter");
    expect(text).toContain("Glasfarben");
    expect(text).not.toContain("Leerungen");
  });
});

describe("Overview — dataset-level loading/empty/error states", () => {
  it("shows the loading state while the summary loads", () => {
    stubRoutes(happyRoutes());
    render(
      <Overview
        lang="en"
        summary={emptySummary}
        summaryLoading={true}
        summaryError={null}
        datasetVersion={0}
        onDemoLoaded={() => {}}
      />,
    );
    expect(document.querySelector('[data-testid="loading-state"]')?.textContent).toContain(
      "Loading overview",
    );
    expect(document.querySelector('[data-testid="overview-keynumbers"]')).toBeNull();
  });

  it("shows the empty state plus demo button when no dataset is loaded", () => {
    stubRoutes(happyRoutes());
    render(
      <Overview
        lang="en"
        summary={emptySummary}
        summaryLoading={false}
        summaryError={null}
        datasetVersion={0}
        onDemoLoaded={() => {}}
      />,
    );
    expect(document.querySelector('[data-testid="empty-state"]')?.textContent).toContain(
      "No dataset loaded yet",
    );
    expect(document.querySelector('[data-testid="demo-load-button"]')?.textContent).toContain(
      "Load demo data",
    );
  });

  it("shows the error state when the summary request fails", () => {
    stubRoutes(happyRoutes());
    render(
      <Overview
        lang="en"
        summary={emptySummary}
        summaryLoading={false}
        summaryError="GET /api/summary failed: 500"
        datasetVersion={0}
        onDemoLoaded={() => {}}
      />,
    );
    const error = document.querySelector('[data-testid="error-state"]');
    expect(error?.textContent).toContain("Could not load the dataset summary");
    expect(error?.textContent).toContain("500");
  });
});

describe("Overview — auto-candidates (today's recommendation)", () => {
  it("POSTs /api/candidates with horizon_days 7 and as_of = summary.date_max", async () => {
    const fetchMock = stubRoutes({
      ...happyRoutes(),
      "POST /api/candidates": () => jsonResponse(selectionFixture),
    });

    render(
      <Overview
        lang="en"
        summary={summaryFixture}
        summaryLoading={false}
        summaryError={null}
        datasetVersion={0}
        onDemoLoaded={() => {}}
      />,
    );
    await flush();
    await flush();

    const call = fetchMock.mock.calls.find(
      (c) => String(c[0]) === "/api/candidates",
    ) as FetchArgs | undefined;
    expect(call).toBeDefined();
    expect(call?.[1]?.method).toBe("POST");
    expect(JSON.parse(call?.[1]?.body as string)).toEqual({
      as_of_date: "2026-10-31", // = summary.date_max, never the wall clock
      horizon_days: 7,
      method: "persistence",
    });

    const text = document.body.textContent ?? "";
    expect(text).toContain("2 containers to empty"); // selectionFixture.selected.length
    expect(text).toContain("1 can wait"); // selectionFixture.skipped.length
    expect(document.querySelector('[data-testid="recommendation-examples"]')?.children.length).toBe(2);
  });

  it("shows a recommendation error state on a malformed candidates payload (never crashes)", async () => {
    stubRoutes({
      ...happyRoutes(),
      "POST /api/candidates": () => jsonResponse({ status: "ok" }),
    });
    render(
      <Overview
        lang="en"
        summary={summaryFixture}
        summaryLoading={false}
        summaryError={null}
        datasetVersion={0}
        onDemoLoaded={() => {}}
      />,
    );
    await flush();
    await flush();

    expect(document.querySelector('[data-testid="error-state"]')?.textContent).toContain(
      "Could not compute the recommendation",
    );
    expect(document.querySelector('[data-testid="overview-root"]')).not.toBeNull();
  });
});

describe("Overview — comparison v2 (scenarios/gains/determinism)", () => {
  it("renders the three-step scenario story with units on every number", async () => {
    stubRoutes(happyRoutes());
    render(
      <Overview
        lang="en"
        summary={summaryFixture}
        summaryLoading={false}
        summaryError={null}
        datasetVersion={0}
        onDemoLoaded={() => {}}
      />,
    );
    await flush();
    await flush();

    expect(document.querySelector('[data-testid="comparison-steps"]')).not.toBeNull();
    const steps = document.body.textContent ?? "";
    // Status quo (real capture values, straight-line-derived; units present).
    expect(steps).toContain("230,865 m");
    expect(steps).toContain("78 / 1,338");
    expect(steps).toContain("5.6 m/kg");
    // Selection-effect sweep.
    expect(steps).toContain("262,995 m");
    expect(steps).toContain("63 / 458");
    expect(steps).toContain("5.0 m/kg");
    // Optimised (median of 5 solves).
    expect(steps).toContain("57,657 m");
    expect(steps).toContain("40 / 458");
    expect(steps).toContain("2.4 m/kg");
    expect(steps).toContain("median of 5 solves");
    // Derived savings: total_gain 173208 / sweep_all 230865 = 75.0 %.
    const savings = document.querySelector('[data-testid="comparison-savings"]')?.textContent ?? "";
    expect(savings).toContain("Derived saving share");
    expect(savings).toContain("75.0 %");
  });

  it("labels the negative selection gain honestly (never spun positive)", async () => {
    stubRoutes(happyRoutes());
    render(
      <Overview
        lang="en"
        summary={summaryFixture}
        summaryLoading={false}
        summaryError={null}
        datasetVersion={0}
        onDemoLoaded={() => {}}
      />,
    );
    await flush();
    await flush();

    const gain = document.querySelector('[data-testid="comparison-selection-gain"]')?.textContent ?? "";
    expect(gain).toContain("−32,130 m");
    expect(gain).toContain("did not pay off");
  });

  it("renders gains with + sign and total gain when positive", async () => {
    stubRoutes(happyRoutes());
    render(
      <Overview
        lang="en"
        summary={summaryFixture}
        summaryLoading={false}
        summaryError={null}
        datasetVersion={0}
        onDemoLoaded={() => {}}
      />,
    );
    await flush();
    await flush();

    const text = document.body.textContent ?? "";
    expect(text).toContain("+205,338 m");
    expect(text).toContain("+173,208 m");
  });

  it("renders nullable per-metrics as — and hides gains without fabricating 0s", async () => {
    stubRoutes({
      ...happyRoutes(),
      "GET /api/comparison": () =>
        jsonResponse({
          ...comparisonFixture,
          scenarios: comparisonFixture.scenarios.map((s) => ({
            ...s,
            distance_per_stop_m: null,
            distance_per_kg_m: null,
          })),
          gains: { selection_gain_m: null, routing_gain_m: null, total_gain_m: null },
        }),
    });
    render(
      <Overview
        lang="en"
        summary={summaryFixture}
        summaryLoading={false}
        summaryError={null}
        datasetVersion={0}
        onDemoLoaded={() => {}}
      />,
    );
    await flush();
    await flush();

    const text = document.body.textContent ?? "";
    expect(text).toContain("— m/kg");
    expect(document.querySelector('[data-testid="comparison-savings"]')).toBeNull();
    expect(
      document.querySelector('[data-testid="comparison-selection-gain"]')?.textContent,
    ).toContain("Gain not available");
  });

  it("shows the identical-determinism statement in technical details", async () => {
    stubRoutes(happyRoutes());
    render(
      <Overview
        lang="en"
        summary={summaryFixture}
        summaryLoading={false}
        summaryError={null}
        datasetVersion={0}
        onDemoLoaded={() => {}}
      />,
    );
    await flush();
    await flush();

    const details = document.querySelector(
      '[data-testid="comparison-tech-details"]',
    ) as HTMLDetailsElement | null;
    details?.setAttribute("open", "true");
    const text = details?.textContent ?? "";
    expect(text).toContain("deterministic: identical distance across 5 solves");
    // Straight-line provenance note stays — never road distance.
    expect(text).toContain("NOT road distance");
  });

  it("shows the median-of-runs wording with the observed spread in technical details", async () => {
    stubRoutes({
      ...happyRoutes(),
      "GET /api/comparison": () => jsonResponse(comparisonMedianOfRunsFixture),
    });
    render(
      <Overview
        lang="en"
        summary={summaryFixture}
        summaryLoading={false}
        summaryError={null}
        datasetVersion={0}
        onDemoLoaded={() => {}}
      />,
    );
    await flush();
    await flush();

    const details = document.querySelector(
      '[data-testid="comparison-tech-details"]',
    ) as HTMLDetailsElement | null;
    details?.setAttribute("open", "true");
    const text = details?.textContent ?? "";
    expect(text).toContain("varied across 5 solves");
    expect(text).toContain("median 57,657 m");
    expect(text).toContain("57,100 m");
    expect(text).toContain("58,300 m");
    expect(text).toContain("NOT road distance");
  });

  it("shows the comparison empty state on 404 (no dataset server-side, not an error)", async () => {
    stubRoutes({
      ...happyRoutes(),
      "GET /api/comparison": () => jsonResponse({ detail: "no dataset" }, 404),
    });
    render(
      <Overview
        lang="en"
        summary={summaryFixture}
        summaryLoading={false}
        summaryError={null}
        datasetVersion={0}
        onDemoLoaded={() => {}}
      />,
    );
    await flush();
    await flush();

    const empty = document.querySelector('[data-testid="comparison-card"] [data-testid="empty-state"]');
    expect(empty?.textContent).toContain("the comparison becomes available after loading data");
    expect(document.querySelector('[data-testid="comparison-steps"]')).toBeNull();
  });

  it("shows a comparison error state on a malformed v2 payload ({status:\"ok\"})", async () => {
    stubRoutes({
      ...happyRoutes(),
      "GET /api/comparison": () => jsonResponse({ status: "ok" }),
    });
    render(
      <Overview
        lang="en"
        summary={summaryFixture}
        summaryLoading={false}
        summaryError={null}
        datasetVersion={0}
        onDemoLoaded={() => {}}
      />,
    );
    await flush();
    await flush();

    const error = document.querySelector('[data-testid="comparison-card"] [data-testid="error-state"]');
    expect(error?.textContent).toContain("Could not compute the comparison");
    expect(error?.textContent).toContain("missing scenarios/gains/determinism");
  });
});

describe("Overview — App.test-style {status:\"ok\"} mocks never crash", () => {
  it("degrades gracefully when every endpoint returns {status:\"ok\"} and the summary is shapeless", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({ status: "ok" }),
      ),
    );
    render(
      <Overview
        lang="en"
        summary={{ status: "ok" } as unknown as DatasetSummary}
        summaryLoading={false}
        summaryError={null}
        datasetVersion={0}
        onDemoLoaded={() => {}}
      />,
    );
    await flush();
    await flush();

    // Root intact, fill stats degrade to "—", comparison degrades to an error
    // state; no exception escaped to any error boundary.
    expect(document.querySelector('[data-testid="overview-root"]')).not.toBeNull();
    expect(document.body.textContent).toContain("— %");
    expect(
      document.querySelector('[data-testid="comparison-card"] [data-testid="error-state"]'),
    ).not.toBeNull();
    expect(document.querySelector('[data-testid="error-boundary"]')).toBeNull();
  });
});
