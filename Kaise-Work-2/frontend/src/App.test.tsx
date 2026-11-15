import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

let root: Root | null = null;

beforeEach(() => {
  (globalThis as unknown as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;
});

afterEach(() => {
  act(() => {
    root?.unmount();
  });
  root = null;
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
});

describe("App", () => {
  it("renders the heading and reports API health from /health", async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(JSON.stringify({ status: "ok" }), {
          headers: { "Content-Type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    await act(async () => {
      root?.render(<App />);
    });

    expect(document.body.textContent).toContain("WasteRouting.AI");
    expect(document.body.textContent).toContain("ok");
    expect(fetchMock).toHaveBeenCalledWith("/health");
  });
});
