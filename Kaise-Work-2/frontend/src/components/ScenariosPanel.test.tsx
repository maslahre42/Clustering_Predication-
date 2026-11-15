/**
 * ScenariosPanel (W4) tests: sliders stay disabled until the config arrives;
 * slider initial values come from the config fixture (never hardcoded);
 * Run POSTs both endpoints with the overrides; cost + service render
 * together with the observed anchor; the mega-day model-consequence note is
 * ALWAYS visible; malformed payloads degrade to an error state.
 */
import { afterEach, describe, expect, it, vi, type Mock } from "vitest";
import { ScenariosPanel } from "./ScenariosPanel";
import { cleanup, click, flush, jsonResponse, render } from "../test/dom";
import { configFixture, scenariosFixture, simulationFixture } from "../test/fixtures";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

type FetchArgs = [input: RequestInfo | URL, init?: RequestInit];

function stubBoth(
  scenarios: unknown,
  simulation: unknown,
  scenariosStatus = 200,
): Mock {
  const fetchMock = vi.fn(async (...args: FetchArgs) => {
    const url = String(args[0]);
    const status = url === "/api/scenarios" ? scenariosStatus : 200;
    return jsonResponse(url === "/api/scenarios" ? scenarios : simulation, status);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("ScenariosPanel — config-gated sliders", () => {
  it("disables sliders and Run until the config has loaded", () => {
    stubBoth(scenariosFixture, simulationFixture);
    render(
      <ScenariosPanel
        lang="en"
        config={null}
        configLoading={true}
        datasetVersion={0}
      />,
    );
    for (const field of [
      "frequency_days",
      "containers_per_series",
      "cost_per_truck_day_eur",
      "max_shift_minutes",
      "vehicle_volume_capacity_litres",
    ]) {
      const slider = document.querySelector(
        `[data-testid="slider-${field}"]`,
      ) as HTMLInputElement | null;
      expect(slider?.disabled).toBe(true);
    }
    const run = document.querySelector('[data-testid="scenarios-run"]') as HTMLButtonElement | null;
    expect(run?.disabled).toBe(true);
    expect(document.body.textContent).toContain("Sliders unlock once the configuration");
  });

  it("seeds slider values from the config fixture and POSTs both endpoints with overrides", async () => {
    const fetchMock = stubBoth(scenariosFixture, simulationFixture);
    render(
      <ScenariosPanel
        lang="en"
        config={configFixture}
        configLoading={false}
        datasetVersion={0}
      />,
    );
    await flush();

    const freq = document.querySelector(
      '[data-testid="slider-frequency_days"]',
    ) as HTMLInputElement | null;
    expect(freq?.disabled).toBe(false);
    expect(freq?.value).toBe(String(configFixture.routing.frequency_days));
    expect(document.body.textContent).toContain(
      configFixture.routing.cost_per_truck_day_eur.toLocaleString("en-US"),
    );

    await click(document.querySelector('[data-testid="scenarios-run"]'));
    await flush();
    await flush();

    const scenarioCall = fetchMock.mock.calls.find((c) => String(c[0]) === "/api/scenarios");
    expect(scenarioCall).toBeDefined();
    expect(JSON.parse(scenarioCall?.[1]?.body as string)).toEqual({
      frequency_days: configFixture.routing.frequency_days,
      routing_config: {
        containers_per_series: configFixture.routing.containers_per_series,
        cost_per_truck_day_eur: configFixture.routing.cost_per_truck_day_eur,
        max_shift_minutes: configFixture.routing.max_shift_minutes,
        vehicle_volume_capacity_litres: configFixture.routing.vehicle_volume_capacity_litres,
      },
    });
    expect(
      fetchMock.mock.calls.find((c) => String(c[0]) === "/api/simulation"),
    ).toBeDefined();
  });
});

describe("ScenariosPanel — results (§6 cost + service together)", () => {
  it("renders anchor, both strategy cards with service rows, TechDetails echo", async () => {
    stubBoth(scenariosFixture, simulationFixture);
    render(
      <ScenariosPanel
        lang="en"
        config={configFixture}
        configLoading={false}
        datasetVersion={0}
      />,
    );
    await flush();
    await click(document.querySelector('[data-testid="scenarios-run"]'));
    await flush();
    await flush();

    const anchor = document.querySelector('[data-testid="scenarios-anchor"]')?.textContent ?? "";
    expect(anchor).toContain("26.9 %");
    expect(anchor).toContain("observed emptying records");

    const fixed = document.querySelector('[data-testid="scenarios-strategy-fixed"]')?.textContent ?? "";
    expect(fixed).toContain("426,000 EUR");
    expect(fixed).toContain("14.4 %"); // service beside cost (§6)
    expect(fixed).toContain("2.4 %");
    const demand = document.querySelector('[data-testid="scenarios-strategy-demand"]')?.textContent ?? "";
    expect(demand).toContain("520,000 EUR");
    expect(demand).toContain("0.0 %");

    const details = document.querySelector(
      '[data-testid="scenarios-tech-details"]',
    ) as HTMLDetailsElement | null;
    details?.setAttribute("open", "true");
    expect(details?.textContent).toContain("frequency_days: 28");
    expect(details?.textContent).toContain("1 series skipped");
  });

  it("always shows the mega-day model-consequence note and data-basis labels", async () => {
    stubBoth(scenariosFixture, simulationFixture);
    render(
      <ScenariosPanel
        lang="en"
        config={configFixture}
        configLoading={false}
        datasetVersion={0}
      />,
    );
    await flush();
    await click(document.querySelector('[data-testid="scenarios-run"]'));
    await flush();
    await flush();

    const note = document.querySelector('[data-testid="timeline-megaday-note"]')?.textContent ?? "";
    expect(note).toContain("Model consequence");
    expect(note).toContain("mega-days");
    const basis = document.querySelector('[data-testid="timeline-basis"]')?.textContent ?? "";
    expect(basis).toContain("records observed");
    expect(basis).toContain("rates derived");
    expect(basis).toContain("plan simulated");
    // Derived spike stat from the response (fixture max = 1,303).
    expect(document.body.textContent).toContain("1,303 collections");
  });

  it("degrades to an error state on a malformed scenarios payload", async () => {
    stubBoth({ status: "ok" }, simulationFixture);
    render(
      <ScenariosPanel
        lang="en"
        config={configFixture}
        configLoading={false}
        datasetVersion={0}
      />,
    );
    await flush();
    await click(document.querySelector('[data-testid="scenarios-run"]'));
    await flush();
    await flush();

    expect(document.querySelector('[data-testid="error-state"]')?.textContent).toContain(
      "Could not run the what-if",
    );
    expect(document.querySelector('[data-testid="scenarios-panel"]')).not.toBeNull();
  });

  it("shows the empty state on 404 (no dataset, §5.3)", async () => {
    stubBoth({ detail: "no dataset" }, { detail: "no dataset" }, 404);
    render(
      <ScenariosPanel
        lang="en"
        config={configFixture}
        configLoading={false}
        datasetVersion={0}
      />,
    );
    await flush();
    await click(document.querySelector('[data-testid="scenarios-run"]'));
    await flush();
    await flush();

    expect(document.querySelector('[data-testid="empty-state"]')?.textContent).toContain(
      "becomes available after loading data",
    );
    expect(document.querySelector('[data-testid="error-state"]')).toBeNull();
  });
});
