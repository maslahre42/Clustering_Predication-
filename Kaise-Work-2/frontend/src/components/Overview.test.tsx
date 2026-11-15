/**
 * Overview page tests (jury-usability pass): EN/DE strings, loading/empty/
 * error states, defensive guards against malformed payloads (App.test mocks
 * return {status:"ok"} for every URL — nothing may crash), the auto-candidates
 * POST body (horizon 7, as_of = date_max) and the derived-savings label rule.
 *
 * Wording discipline (docs/contracts.md §1.5/§5.2.2 v4 flip): every row is an
 * **emptying record** (DE "Leerungsdaten") [representative-stated] — human
 * strings say so; JSON field names keep the historical `readings` tokens.
 */
import { afterEach, describe, expect, it, vi, type Mock } from "vitest";
import { Overview } from "./Overview";
import type { DatasetSummary } from "../lib/api";
import { cleanup, flush, jsonResponse, render } from "../test/dom";
import {
  comparisonFixture,
  comparisonMedianOfRunsFixture,
  daysToFullFixture,
  scenariosFixture,
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
  "GET /api/days-to-full": () => jsonResponse(daysToFullFixture),
  // W1/W2 toggle card (server defaults, empty body).
  "POST /api/scenarios": () => jsonResponse(scenariosFixture),
});

const emptySummary: DatasetSummary | null = null;

describe("Overview — wording discipline", () => {
  it("renders EN strings with the v4 'emptying records' wording (every row is one emptying event)", async () => {
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
    expect(text).toContain("Emptying records with full containers");
    expect(text).toContain("10.2 %");
    // Threshold note interpolated from fill_stats, not hardcoded.
    expect(text).toContain("at or above 80 % fill");
    // v4 wording flip: human strings name the emptying records (§1.5).
    expect(text).toContain("emptying records");
  });

  it("renders DE strings with the 'Leerungsdaten' wording", async () => {
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
    expect(text).toContain("Leerungsdaten mit vollem Behälter");
    expect(text).toContain("Glasfarben");
    // v4 wording flip (§1.5); "Leerungen" alone is a substring of
    // "Leerungsdaten" — asserted via the full word instead.
    expect(text).toContain("Leerungsdaten");
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
    expect(steps).toContain("355,474 m");
    expect(steps).toContain("60 / 637");
    expect(steps).toContain("10.5 m/kg");
    // Sweep-all upper bound.
    expect(steps).toContain("454,623 m");
    expect(steps).toContain("50 / 1,338");
    expect(steps).toContain("12.6 m/kg");
    // Selection-effect sweep.
    expect(steps).toContain("527,021 m");
    expect(steps).toContain("38 / 458");
    expect(steps).toContain("13.2 m/kg");
    // Optimised (median of 5 solves).
    expect(steps).toContain("70,175 m");
    expect(steps).toContain("34 / 458");
    expect(steps).toContain("3.9 m/kg");
    expect(steps).toContain("median of 5 solves");
    // v3 per-scenario cost rows (3 trucks in use × 500 EUR/truck-day [predicted]).
    expect(steps).toContain("1,500 EUR/day · 300,000 EUR/year");
    // Derived savings: total_gain 384448 / sweep_all 454623 = 84.6 %.
    const savings = document.querySelector('[data-testid="comparison-savings"]')?.textContent ?? "";
    expect(savings).toContain("Derived saving share");
    expect(savings).toContain("84.6 %");
    // v3 fleet-budget card (ortools fleet recommendation priced at §4.6 rates).
    const budget = document.querySelector('[data-testid="fleet-budget"]')?.textContent ?? "";
    expect(budget).toContain("Fleet budget");
    expect(budget).toContain("99 vehicles");
    expect(budget).toContain("49,500 EUR");
    expect(budget).toContain("9,900,000 EUR");
    expect(budget).toContain("predicted");
    // v3 days-to-full KPI ([predicted] estimates from emptying records; all
    // numbers from the API, never hardcoded).
    const dtf = document.querySelector('[data-testid="keynum-days-to-full"]')?.textContent ?? "";
    expect(dtf).toContain("59.3 d");
    expect(dtf).toContain("1,303");
    expect(dtf).toContain("1,338");
    expect(dtf).toContain("fill_at_emptying_rate");
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
    expect(gain).toContain("−72,398 m");
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
    expect(text).toContain("+456,846 m");
    expect(text).toContain("+384,448 m");
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
    expect(text).toContain("median 70,175 m");
    expect(text).toContain("69,800 m");
    expect(text).toContain("70,900 m");
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

describe("Overview — filling-time tanks (W3, §5.2.3 v2 stats_by_material)", () => {
  it("renders per-material tanks with lower-bound notes and the mandatory §1.5 caveat", async () => {
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

    const tanks = document.querySelector('[data-testid="filling-tanks"]')?.textContent ?? "";
    expect(tanks).toContain("Filling time per material");
    // Median days per material — fixture values (real-capture traced).
    expect(tanks).toContain("121.9 d");
    expect(tanks).toContain("52.0 d");
    expect(tanks).toContain("38.1 d");
    // Target % interpolated from the response, never hardcoded.
    expect(tanks).toContain("90 %");
    // Lower-bound notes per material (fixture lb shares 36.3/73.6/88.5).
    expect(tanks).toContain("36.3 %");
    expect(tanks).toContain("73.6 %");
    expect(tanks).toContain("88.5 %");
    // Mandatory §1.5 caveat rendered verbatim from the API assumptions.
    const caveat = document.querySelector('[data-testid="tanks-caveat"]')?.textContent ?? "";
    expect(caveat).toContain("not how fast it would have filled");
    expect(caveat).toContain("no unobserved emptying between records");
  });

  it("hides the tanks section when stats_by_material is missing (degrades, never crashes)", async () => {
    stubRoutes({
      ...happyRoutes(),
      "GET /api/days-to-full": () => {
        const { stats_by_material, ...rest } = daysToFullFixture;
        return jsonResponse(rest);
      },
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

    expect(document.querySelector('[data-testid="filling-tanks"]')).toBeNull();
    expect(document.querySelector('[data-testid="overview-root"]')).not.toBeNull();
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
