/**
 * ContainersIntervalPanel (W9) tests: §5.2.3 v2 rows render from the
 * days-to-full payload; the "at least" marker only on `is_lower_bound` rows;
 * no-estimate rows carry their API reason; filters (material, lower-bound,
 * without-estimate, location prefix) work; the mandatory §1.5 caveat is
 * present; loading/empty/error states.
 */
import { afterEach, describe, expect, it, vi, type Mock } from "vitest";
import { ContainersIntervalPanel } from "./ContainersIntervalPanel";
import { cleanup, click, flush, jsonResponse, render, setInputValue, setSelectValue } from "../test/dom";
import { daysToFullFixture } from "../test/fixtures";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function stubDays(payload: unknown, status = 200): Mock {
  const fetchMock = vi.fn(async () => jsonResponse(payload as object, status));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("ContainersIntervalPanel — rows", () => {
  it("renders rate/interval/days-to-full with 'at least' markers and reasons", async () => {
    // One fixture row uses a SHORT id (≤ 13 chars) — must render without a
    // trailing ellipsis (review pass 2: ellipsis only when actually truncated).
    const withShortId = {
      ...daysToFullFixture,
      series: [
        { ...daysToFullFixture.series[0], location_id: "short-id-01" },
        ...daysToFullFixture.series.slice(1),
      ],
    };
    stubDays(withShortId);
    render(<ContainersIntervalPanel lang="en" datasetVersion={0} />);
    await flush();
    await flush();

    const rows = document.querySelector('[data-testid="interval-rows"]')?.textContent ?? "";
    // Brown row (fixture): rate 2.083333 pp/d, interval 34 d, 43.2 d, lower bound.
    expect(rows).toContain("2.08 pp/d");
    expect(rows).toContain("34.0 d");
    expect(rows).toContain("43.2 d");
    expect(rows).toContain("2026-10-23"); // predicted_full_date, never clamped
    // Short id rendered whole — no ellipsis appended.
    expect(rows).toContain("short-id-01");
    expect(rows).not.toContain("short-id-01…");
    // Long id still truncates with the ellipsis.
    expect(rows).toContain("11111111-2222…");
    const markers = document.querySelectorAll('[data-testid="interval-at-least"]');
    expect(markers.length).toBe(1); // only the is_lower_bound row
    // White row has no estimate — reason shown, never fabricated.
    expect(rows).toContain("no estimate: no_numeric_fill");
    // Days-to-target column header interpolates the API target (90 %).
    expect(document.body.textContent).toContain("Days to 90 %");
    // Mandatory §1.5 caveat from the API assumptions.
    const caveat = document.querySelector('[data-testid="interval-caveat"]')?.textContent ?? "";
    expect(caveat).toContain("not how fast it would have filled");
  });

  it("filters by material, lower-bound, without-estimate and location prefix", async () => {
    stubDays(daysToFullFixture);
    render(<ContainersIntervalPanel lang="en" datasetVersion={0} />);
    await flush();
    await flush();

    const count = () =>
      document.querySelectorAll('[data-testid="interval-rows"] tr').length;

    // Material filter (controlled select — native setter so React sees it).
    const select = document.querySelector(
      '[data-testid="interval-filter-material"]',
    ) as HTMLSelectElement | null;
    expect(select).not.toBeNull();
    setSelectValue(select!, "white");
    await flush();
    expect(count()).toBe(1);
    expect(document.querySelector('[data-testid="interval-rows"]')?.textContent).toContain(
      "no estimate: no_numeric_fill",
    );

    // Lower-bound-only filter — BOTH fixture rows carry is_lower_bound: true
    // (§5.2.3: overfull records set the flag even without a numeric rate).
    const lb = document.querySelector(
      '[data-testid="interval-filter-lowerbound"]',
    ) as HTMLInputElement | null;
    setSelectValue(select!, "all");
    await click(lb);
    expect(count()).toBe(2);
    expect(document.querySelector('[data-testid="interval-rows"]')?.textContent).toContain("43.2 d");
    expect(document.querySelector('[data-testid="interval-rows"]')?.textContent).toContain(
      "no estimate: no_numeric_fill",
    );

    // Without-estimate filter.
    const noEst = document.querySelector(
      '[data-testid="interval-filter-noestimate"]',
    ) as HTMLInputElement | null;
    await click(lb); // back to unchecked
    await click(noEst);
    expect(count()).toBe(1);
    expect(document.querySelector('[data-testid="interval-rows"]')?.textContent).toContain(
      "no estimate",
    );
    await click(noEst); // reset

    // Location prefix search (controlled input — native setter).
    const search = document.querySelector(
      '[data-testid="interval-filter-search"]',
    ) as HTMLInputElement | null;
    setInputValue(search!, "11111111");
    await flush();
    expect(count()).toBe(1);
    expect(document.querySelector('[data-testid="interval-rows"]')?.textContent).toContain("white");
  });
});

describe("ContainersIntervalPanel — states", () => {
  it("shows loading, then the empty state on 404 (no dataset, §5.3)", async () => {
    stubDays({ detail: "no dataset" }, 404);
    render(<ContainersIntervalPanel lang="en" datasetVersion={0} />);
    expect(document.querySelector('[data-testid="loading-state"]')?.textContent).toContain(
      "Loading per-container intervals",
    );
    await flush();
    await flush();
    expect(document.querySelector('[data-testid="empty-state"]')?.textContent).toContain(
      "become available after loading data",
    );
  });

  it("shows the error state on a malformed payload (never crashes)", async () => {
    stubDays({ status: "ok" });
    render(<ContainersIntervalPanel lang="en" datasetVersion={0} />);
    await flush();
    await flush();
    expect(document.querySelector('[data-testid="error-state"]')?.textContent).toContain(
      "Could not load the per-container intervals",
    );
    expect(document.querySelector('[data-testid="containers-interval"]')).not.toBeNull();
  });

  it("shows the no-matches empty state when filters exclude everything", async () => {
    stubDays(daysToFullFixture);
    render(<ContainersIntervalPanel lang="en" datasetVersion={0} />);
    await flush();
    await flush();
    const search = document.querySelector(
      '[data-testid="interval-filter-search"]',
    ) as HTMLInputElement | null;
    setInputValue(search!, "zzzzzzzz");
    await flush();
    expect(document.querySelector('[data-testid="empty-state"]')?.textContent).toContain(
      "No series match the current filters",
    );
  });
});
