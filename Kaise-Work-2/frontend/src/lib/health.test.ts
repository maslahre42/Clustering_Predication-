import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchHealth } from "./health";

describe("fetchHealth", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns the parsed health payload from GET /health", async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(JSON.stringify({ status: "ok" }), {
          headers: { "Content-Type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const payload = await fetchHealth();

    expect(payload).toEqual({ status: "ok" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith("/health");
  });

  it("throws when the API responds with an error status", async () => {
    const fetchMock = vi.fn(async () => new Response("boom", { status: 500 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchHealth()).rejects.toThrow("GET /health failed: 500");
  });
});
