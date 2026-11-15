/**
 * Regression test for the blank-page-after-upload bug (2026-11-14).
 *
 * Drives the FULL real request sequence with verbatim captured payloads
 * (frontend/src/test/fixtures/real-capture/, observed 2026-11-14 from the live
 * backend after uploading data/raw/glass_fill_levels_anonymized_f.csv):
 * mount GETs 404 → user uploads the CSV → POST /api/datasets 200 (flat
 * DatasetSummary + errors/warnings) → App refetches containers/summary →
 * dashboard renders.
 *
 * Bug history: the API client assumed a nested `{ summary, errors, warnings }`
 * upload shape; the real payload is flat, so `response.summary` was `undefined`,
 * the first post-upload render threw (uncaught) and React unmounted the whole
 * tree — a blank page before any refetch effect could run.
 */
import uploadJson from "./test/fixtures/real-capture/upload.json";
import summaryJson from "./test/fixtures/real-capture/summary.json";
import containersJson from "./test/fixtures/real-capture/containers.json";
import configJson from "./test/fixtures/real-capture/config.json";
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import App from "./App";
import { click, cleanup, flush, render } from "./test/dom";

type FetchArgs = [input: RequestInfo | URL, init?: RequestInit];

beforeEach(() => {
  (globalThis as unknown as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Sets files on a jsdom file input (jsdom has no DataTransfer-based FileList). */
function setFiles(input: HTMLInputElement, file: File): void {
  Object.defineProperty(input, "files", {
    value: { 0: file, length: 1, item: (i: number) => (i === 0 ? file : null) },
    configurable: true,
  });
}

async function renderAppWithRealSequence(fetchMock: Mock) {
  const view = render(<App />);
  await flush();
  await flush();
  expect(fetchMock.mock.calls.length).toBeGreaterThan(0);
  return view;
}

describe("upload flow with real captured payloads (blank-page regression)", () => {
  it("renders the dashboard after uploading the real CSV — no blank page", async () => {
    let uploaded = false;
    const fetchMock = vi.fn(async (...args: FetchArgs) => {
      const [rawInput, init] = args;
      const path = String(rawInput);
      const method = init?.method ?? "GET";
      if (method === "POST" && path === "/api/datasets") {
        uploaded = true;
        return jsonResponse(uploadJson);
      }
      if (method === "GET" && path === "/health") {
        return jsonResponse({ status: "ok", service: "wasterouting-api" });
      }
      if (method === "GET" && path === "/api/summary") {
        return uploaded ? jsonResponse(summaryJson) : jsonResponse({ detail: "no dataset" }, 404);
      }
      if (method === "GET" && path === "/api/containers") {
        return uploaded
          ? jsonResponse(containersJson)
          : jsonResponse({ detail: "no dataset" }, 404);
      }
      if (method === "GET" && path === "/api/config") {
        return jsonResponse(configJson);
      }
      throw new Error(`unexpected fetch ${method} ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const view = await renderAppWithRealSequence(fetchMock);

    // Drive the actual upload through the file input + submit.
    const input = view.querySelector('input[data-testid="upload-input"]');
    expect(input).not.toBeNull();
    setFiles(input as HTMLInputElement, new File(["location_id,material_type,date,fill_level"], "glass_fill_levels_anonymized_f.csv", { type: "text/csv" }));
    await click(view.querySelector('button[data-testid="upload-submit"]'));
    await flush();
    await flush();
    await flush();

    // The page must not be blank and must show the real upload result.
    expect(document.body.textContent).toContain("WasteRouting.AI");
    const uploadSummary = view.querySelector('[data-testid="upload-summary"]');
    expect(uploadSummary).not.toBeNull();
    expect(uploadSummary?.textContent).toContain("glass_fill_levels_anonymized_f.csv");
    expect(uploadSummary?.textContent).toContain("dataset active");

    // KPI overview shows the real observed counts (11,701 rows / 1,338 series).
    const kpi = view.querySelector('[data-testid="kpi-grid"]');
    expect(kpi).not.toBeNull();
    expect(kpi?.textContent).toContain("11,701 rows");

    // Container list refetched and shows the real series + overfull counts.
    const count = view.querySelector('[data-testid="container-count"]');
    expect(count?.textContent).toContain("1338 series");
    expect(count?.textContent).toContain("101 currently overfull");

    // POST then refetches: containers + summary GETs fired after the upload.
    const postIndex = fetchMock.mock.calls.findIndex(
      (c) => String(c[0]) === "/api/datasets",
    );
    expect(postIndex).toBeGreaterThanOrEqual(0);
    const refetches = fetchMock.mock.calls
      .slice(postIndex + 1)
      .map((c) => String(c[0]));
    expect(refetches).toContain("/api/containers");
    expect(refetches).toContain("/api/summary");

    // Healthy path: no error boundary fallback anywhere.
    expect(view.querySelector('[data-testid="error-boundary"]')).toBeNull();
  });

  it("overfull rows render the overfull badge with null fill — never coerced to 100", async () => {
    const overfull = (containersJson as { last_is_overfull: boolean; last_fill_pct: number | null }[])
      .filter((r) => r.last_is_overfull && r.last_fill_pct === null).length;
    expect(overfull).toBe(101); // real-capture edge values are present in the fixture

    const fetchMock = vi.fn(async (...args: FetchArgs) => {
      const [rawInput, init] = args;
      const path = String(rawInput);
      const method = init?.method ?? "GET";
      if (method === "GET" && path === "/api/containers") return jsonResponse(containersJson);
      if (method === "GET" && path === "/health") {
        return jsonResponse({ status: "ok", service: "wasterouting-api" });
      }
      return jsonResponse({ detail: "no dataset" }, 404);
    });
    vi.stubGlobal("fetch", fetchMock);

    const view = await renderAppWithRealSequence(fetchMock);
    await click(view.querySelector('[data-testid="containers-panel"] button') ?? null);
    // "Show all 1338 series" expands; overfull badges render for null-fill rows.
    const badges = view.querySelectorAll('[data-testid="overfull-badge"]');
    expect(badges.length).toBe(101);
  });
});
