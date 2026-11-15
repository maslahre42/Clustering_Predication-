import { afterEach, describe, expect, it, vi } from "vitest";
import { CandidatesPanel } from "./CandidatesPanel";
import { click, cleanup, jsonResponse, render } from "../test/dom";
import { selectionFixture } from "../test/fixtures";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("CandidatesPanel", () => {
  it("runs selection and renders reason badges for selected and skipped stops", async () => {
    const fetchMock = vi.fn(
      async (_url: RequestInfo | URL, _init?: RequestInit): Promise<Response> =>
        jsonResponse(selectionFixture),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<CandidatesPanel defaultAsOf="2026-10-31" policyOverride={{}} />);
    await click(document.querySelector('[data-testid="candidates-run"]'));

    // Request carried the §5.2 CandidateRequest body.
    const [url, init] = fetchMock.mock.calls[0] as [RequestInfo | URL, RequestInit | undefined];
    expect(String(url)).toBe("/api/candidates");
    const body = JSON.parse(init?.body as string) as Record<string, unknown>;
    expect(body.as_of_date).toBe("2026-10-31");
    expect(body.horizon_days).toBe(28);
    expect(body.method).toBe("persistence");
    expect(body.policy_config).toEqual({});

    // Reason codes + details + counts visible, selected vs skipped separated.
    const text = document.body.textContent ?? "";
    expect(text).toContain("at or above threshold");
    expect(text).toContain("overfull state");
    expect(text).toContain("below threshold");
    expect(text).toContain("predicted 92.0 >= threshold 80 + buffer 0");
    expect(document.querySelector('[data-testid="selected-rows"]')?.children.length).toBe(2);
    expect(document.querySelector('[data-testid="skipped-rows"]')?.children.length).toBe(1);
    expect(document.querySelector('[data-testid="selection-result"]')?.textContent).toContain(
      "selected 2",
    );
    // Effective config echo stays labelled as demo assumption.
    expect(text).toContain("all [demo assumption]");
  });

  it("shows an error state when the API rejects the request", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ detail: "as_of_date out of dataset range" }, 422)),
    );

    render(<CandidatesPanel defaultAsOf="2026-10-31" policyOverride={{}} />);
    await click(document.querySelector('[data-testid="candidates-run"]'));

    expect(document.querySelector('[data-testid="error-state"]')?.textContent).toContain(
      "Candidate selection failed",
    );
  });
});
