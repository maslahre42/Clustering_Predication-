/**
 * PresentationMode (W5) tests: 6 slides with step counter; ←/→ navigation and
 * Esc close (window-level keydown); honesty labels on every slide (§6 —
 * basis lines, §1.5 caveat, straight-line note, simulation basis);
 * per-slide fallbacks: a failing source renders the explicit "data not
 * available" note, never a fabricated number; bounds disable prev/next.
 * jsdom has no requestFullscreen — the component must tolerate that.
 */
import { afterEach, describe, expect, it, vi, type Mock } from "vitest";
import { act } from "react";
import { PresentationMode } from "./PresentationMode";
import { cleanup, flush, jsonResponse, render } from "../test/dom";
import {
  comparisonFixture,
  daysToFullFixture,
  scenariosFixture,
  selectionFixture,
  summaryWithFillStats,
} from "../test/fixtures";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

type FetchArgs = [input: RequestInfo | URL, init?: RequestInit];

function stubRoutes(routes: Record<string, (args: FetchArgs) => Response>): Mock {
  const fetchMock = vi.fn(async (...args: FetchArgs) => {
    const key = `${args[1]?.method ?? "GET"} ${String(args[0])}`;
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
  "GET /api/comparison": () => jsonResponse(comparisonFixture),
  "POST /api/scenarios": () => jsonResponse(scenariosFixture),
  "GET /api/days-to-full": () => jsonResponse(daysToFullFixture),
  "POST /api/candidates": () => jsonResponse(selectionFixture),
});

/** Advance/collapse via the window-level key handler (inside act). */
async function pressKey(key: string): Promise<void> {
  await act(async () => {
    window.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
  });
  await flush();
}

describe("PresentationMode — slides & navigation", () => {
  it("opens on slide 1 with the step counter and slide-1 basis label", async () => {
    stubRoutes(happyRoutes());
    const onClose = vi.fn();
    render(
      <PresentationMode lang="en" summary={summaryWithFillStats} onClose={onClose} />,
    );
    await flush();

    const text = document.body.textContent ?? "";
    expect(document.querySelector('[data-testid="presentation-root"]')).not.toBeNull();
    expect(text).toContain("Step 1 of 6");
    expect(text).toContain("Why we are here");
    expect(text).toContain("observed data, predictions and demo assumptions");
    // Honesty labels are visible, not tucked away.
    expect(text).toContain("← → to navigate");
  });

  it("ArrowRight advances to the observed slide with anchor + basis; ArrowLeft returns", async () => {
    stubRoutes(happyRoutes());
    render(
      <PresentationMode lang="en" summary={summaryWithFillStats} onClose={() => {}} />,
    );
    await flush();
    await flush();

    await pressKey("ArrowRight");
    const text = document.body.textContent ?? "";
    expect(text).toContain("Step 2 of 6");
    expect(text).toContain("Observed today");
    // 10.2 % from summary fill_stats; anchor 26.9 % from the comparison.
    expect(text).toContain("10.2 %");
    expect(text).toContain("26.9 %");
    expect(text).toContain("observed emptying records [observed]");

    await pressKey("ArrowLeft");
    expect(document.body.textContent ?? "").toContain("Step 1 of 6");
  });

  it("slide 3 keeps the §1.5 caveat and lower-bound labels visible", async () => {
    stubRoutes(happyRoutes());
    render(
      <PresentationMode lang="en" summary={summaryWithFillStats} onClose={() => {}} />,
    );
    await flush();
    await flush();

    await pressKey("ArrowRight");
    await pressKey("ArrowRight");
    const text = document.body.textContent ?? "";
    expect(text).toContain("Step 3 of 6");
    expect(text).toContain("121.9 d");
    expect(text).toContain("at least (36.3 % lower bounds)");
    // Mandatory §1.5 caveat (first API assumption, verbatim).
    expect(text).toContain("not how fast it would have filled");
    expect(text).toContain("predicted from emptying records");
  });

  it("slide 5 shows cost WITH service and the honest more-expensive flag", async () => {
    stubRoutes(happyRoutes());
    render(
      <PresentationMode lang="en" summary={summaryWithFillStats} onClose={() => {}} />,
    );
    await flush();
    await flush();

    for (let i = 0; i < 4; i += 1) await pressKey("ArrowRight");
    const text = document.body.textContent ?? "";
    expect(text).toContain("Step 5 of 6");
    expect(text).toContain("426,000 EUR");
    expect(text).toContain("520,000 EUR");
    expect(text).toContain("overflow container-days");
    expect(text).toContain("costs MORE");
    expect(text).toContain("simulation based on historical rates");
  });

  it("slide 6 shows straight-line-labelled distances and derived savings", async () => {
    stubRoutes(happyRoutes());
    render(
      <PresentationMode lang="en" summary={summaryWithFillStats} onClose={() => {}} />,
    );
    await flush();
    await flush();

    for (let i = 0; i < 5; i += 1) await pressKey("ArrowRight");
    const text = document.body.textContent ?? "";
    expect(text).toContain("Step 6 of 6");
    expect(text).toContain("454,623 m");
    expect(text).toContain("70,175 m");
    expect(text).toContain("84.6 %"); // 384,448 / 454,623, derived
    expect(text).toContain("NOT road distance");
  });

  it("slide 5 words an exactly-zero cost delta neutrally, never as ± costs", async () => {
    // costDelta derives from cost_eur_per_year — equalise THAT (250,000 both
    // → delta 0). Totals may differ; the delta line keys on per-year.
    const equalCost = {
      ...scenariosFixture,
      strategies: scenariosFixture.strategies.map((s) => ({
        ...s,
        cost_eur_per_year: 250000,
      })),
    };
    stubRoutes({
      ...happyRoutes(),
      "POST /api/scenarios": () => jsonResponse(equalCost),
    });
    render(
      <PresentationMode lang="en" summary={summaryWithFillStats} onClose={() => {}} />,
    );
    await flush();
    await flush();

    for (let i = 0; i < 4; i += 1) await pressKey("ArrowRight");
    const text = document.body.textContent ?? "";
    // Zero-delta branch (delta = 250,000 − 250,000 = 0): neutral wording.
    expect(text).toContain("Same simulated cost for today and the plan");
    expect(text).not.toContain("costs MORE");
    expect(text).not.toContain("costs LESS");
    expect(text).not.toContain("−0 EUR/year");
  });

  it("Esc closes via onClose; ArrowRight is bounded at the last slide", async () => {
    stubRoutes(happyRoutes());
    const onClose = vi.fn();
    render(
      <PresentationMode lang="en" summary={summaryWithFillStats} onClose={onClose} />,
    );
    await flush();

    for (let i = 0; i < 10; i += 1) await pressKey("ArrowRight");
    expect(document.body.textContent ?? "").toContain("Step 6 of 6");
    const next = document.querySelector(
      '[data-testid="presentation-next"]',
    ) as HTMLButtonElement | null;
    expect(next?.disabled).toBe(true);

    await pressKey("Escape");
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

describe("PresentationMode — per-slide fallbacks (§6 honesty)", () => {
  it("renders the explicit unavailable note when the slide's source 404s (no crash, no fake numbers)", async () => {
    stubRoutes({
      "GET /api/comparison": () => jsonResponse({ detail: "no dataset" }, 404),
      "POST /api/scenarios": () => jsonResponse({ detail: "no dataset" }, 404),
      "GET /api/days-to-full": () => jsonResponse({ detail: "no dataset" }, 404),
      "POST /api/candidates": () => jsonResponse({ detail: "no dataset" }, 404),
    });
    render(
      <PresentationMode lang="en" summary={summaryWithFillStats} onClose={() => {}} />,
    );
    await flush();
    await flush();

    // Slide 5 (cost+service) depends ONLY on POST /api/scenarios — a fetched
    // source. Slide 2 still shows the summary-prop fill stats honestly.
    for (let i = 0; i < 4; i += 1) await pressKey("ArrowRight");
    const text = document.body.textContent ?? "";
    expect(text).toContain("Step 5 of 6");
    expect(text).toContain("Data not available for this step.");
    expect(text).not.toContain("426,000 EUR"); // no fabricated values
    expect(document.querySelector('[data-testid="presentation-root"]')).not.toBeNull();
  });

  it("shows the loading note on a data slide while the fetches are pending", async () => {
    // Never-resolving fetches keep every slice in the loading state.
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Promise<Response>(() => {})),
    );
    render(
      <PresentationMode lang="en" summary={summaryWithFillStats} onClose={() => {}} />,
    );
    await pressKey("ArrowRight");
    expect(document.body.textContent).toContain("Loading data…");
    await flush();
    await flush();
  });

  it("renders German strings with parity (slide 1 + footer)", async () => {
    stubRoutes(happyRoutes());
    render(
      <PresentationMode lang="de" summary={summaryWithFillStats} onClose={() => {}} />,
    );
    await flush();

    const text = document.body.textContent ?? "";
    expect(text).toContain("Schritt 1 von 6");
    expect(text).toContain("Warum wir hier sind");
    expect(text).toContain("beobachtete Daten, Prognosen und Demo-Annahmen");
    expect(text).toContain("Alle Werte gelabelt");
  });
});
