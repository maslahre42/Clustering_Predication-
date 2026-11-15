/**
 * DemoLoadButton tests (§5.1 POST /api/datasets/demo): request has no body,
 * success forwards the flat upload response, busy and error states are shown.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { DemoLoadButton } from "./DemoLoadButton";
import type { DatasetSummary, UploadResponse } from "../lib/api";
import { click, cleanup, flush, jsonResponse, render } from "../test/dom";

type FetchArgs = [input: RequestInfo | URL, init?: RequestInit];

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const demoUploadResponse: UploadResponse = {
  n_rows: 11701,
  n_locations: 449,
  n_series: 1338,
  date_min: "2025-01-01",
  date_max: "2026-10-31",
  rows_per_material: { brown: 3901, green: 3900, white: 3900 },
  n_errors: 0,
  n_warnings: 0,
  source_name: "demo:glass_fill_levels_anonymized_f.csv",
  errors: [],
  warnings: [],
};

function renderButton(onLoaded: (summary: DatasetSummary) => void = () => {}) {
  return render(<DemoLoadButton lang="en" onLoaded={onLoaded} />);
}

describe("DemoLoadButton", () => {
  it("POSTs /api/datasets/demo with no request body and forwards the response", async () => {
    const fetchMock = vi.fn(async (..._args: FetchArgs): Promise<Response> =>
      jsonResponse(demoUploadResponse),
    );
    vi.stubGlobal("fetch", fetchMock);
    const onLoaded = vi.fn();

    const view = renderButton(onLoaded);
    await click(view.querySelector('[data-testid="demo-load-button"]'));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as FetchArgs;
    expect(url).toBe("/api/datasets/demo");
    expect(init?.method).toBe("POST");
    expect(init?.body).toBeUndefined();
    expect(onLoaded).toHaveBeenCalledTimes(1);
    expect(onLoaded.mock.calls[0]?.[0].source_name).toBe("demo:glass_fill_levels_anonymized_f.csv");
    expect(view.querySelector('[data-testid="error-state"]')).toBeNull();
  });

  it("shows a busy state (disabled button + loading label) while the request is in flight", async () => {
    let resolveFetch!: (r: Response) => void;
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise<Response>((resolve) => {
            resolveFetch = resolve;
          }),
      ),
    );

    const view = renderButton();
    await click(view.querySelector('[data-testid="demo-load-button"]'));

    const button = view.querySelector('[data-testid="demo-load-button"]') as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(button.textContent).toContain("Loading demo data");
    expect(document.querySelector('[data-testid="loading-state"]')?.textContent).toContain(
      "Loading demo data",
    );

    resolveFetch(jsonResponse(demoUploadResponse));
    await flush();
    expect((view.querySelector('[data-testid="demo-load-button"]') as HTMLButtonElement).disabled).toBe(false);
  });

  it("shows an error state when the demo endpoint fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ detail: "demo dataset missing" }, 500)),
    );

    const view = renderButton();
    await click(view.querySelector('[data-testid="demo-load-button"]'));

    const error = document.querySelector('[data-testid="error-state"]');
    expect(error?.textContent).toContain("Could not load demo data");
    expect(error?.textContent).toContain("demo dataset missing");
  });
});
