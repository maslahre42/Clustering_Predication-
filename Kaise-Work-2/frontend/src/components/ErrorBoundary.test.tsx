/**
 * ErrorBoundary tests: a render error in one view shows a visible fallback
 * (message + retry) instead of a blank page, other content survives, and
 * retry re-renders the subtree once the underlying issue is gone.
 */
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ErrorBoundary } from "./ErrorBoundary";
import { click, cleanup, flush, render } from "../test/dom";

beforeEach(() => {
  (globalThis as unknown as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

/** Throws on render while `armed`. */
function Bomb({ armed }: { armed: boolean }) {
  if (armed) throw new Error("synthetic render failure");
  return <p data-testid="bomb-ok">recovered content</p>;
}

describe("ErrorBoundary", () => {
  it("shows a visible fallback with the error message and a retry button, siblings unaffected", async () => {
    // Keep the expected console.error noise out of the test output.
    vi.spyOn(console, "error").mockImplementation(() => {});

    const view = render(
      <div>
        <p data-testid="sibling">dashboard header</p>
        <ErrorBoundary label="Test panel">
          <Bomb armed={true} />
        </ErrorBoundary>
      </div>,
    );
    await flush();

    const fallback = view.querySelector('[data-testid="error-boundary"]');
    expect(fallback).not.toBeNull();
    expect(fallback?.textContent).toContain("Test panel");
    expect(fallback?.textContent).toContain("synthetic render failure");
    expect(view.querySelector('[data-testid="error-boundary-retry"]')).not.toBeNull();
    // No blank page: sibling content outside the boundary still renders.
    expect(view.querySelector('[data-testid="sibling"]')?.textContent).toBe("dashboard header");
  });

  it("retry re-renders the subtree after the error is resolved", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});

    function Harness() {
      const [armed, setArmed] = useState(true);
      return (
        <div>
          <button
            type="button"
            data-testid="fix"
            onClick={() => setArmed(false)}
          >
            fix
          </button>
          <ErrorBoundary label="Retry panel">
            <Bomb armed={armed} />
          </ErrorBoundary>
        </div>
      );
    }

    const view = render(<Harness />);
    await flush();
    expect(view.querySelector('[data-testid="error-boundary"]')).not.toBeNull();

    // Underlying issue resolved (prop no longer throws), then retry.
    await click(view.querySelector('[data-testid="fix"]'));
    await click(view.querySelector('[data-testid="error-boundary-retry"]'));

    expect(view.querySelector('[data-testid="error-boundary"]')).toBeNull();
    expect(view.querySelector('[data-testid="bomb-ok"]')?.textContent).toBe("recovered content");
  });

  it("retry with a still-throwing subtree returns to the fallback (never blank)", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});

    const view = render(
      <ErrorBoundary label="Still broken">
        <Bomb armed={true} />
      </ErrorBoundary>,
    );
    await flush();
    expect(view.querySelector('[data-testid="error-boundary"]')).not.toBeNull();

    await click(view.querySelector('[data-testid="error-boundary-retry"]'));

    expect(view.querySelector('[data-testid="error-boundary"]')).not.toBeNull();
    expect(view.querySelector('[data-testid="error-boundary"]')?.textContent).toContain(
      "Still broken",
    );
  });
});
