import { afterEach, describe, expect, it, vi } from "vitest";
import { ContainerList } from "./ContainerList";
import { cleanup, flush, jsonResponse, render } from "../test/dom";
import { containersFixture } from "../test/fixtures";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("ContainerList", () => {
  it("renders series with last fill and a distinct overfull badge", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(containersFixture)),
    );

    render(<ContainerList datasetVersion={0} />);
    await flush();

    const overfullBadge = document.querySelector('[data-testid="overfull-badge"]');
    expect(overfullBadge?.textContent).toBe("overfull");
    expect(document.querySelector('[data-testid="container-count"]')?.textContent).toContain(
      "1 currently overfull",
    );
    // Numeric fill keeps its percent unit; overfull shown as its own state (never 100 %).
    const rowsText = document.querySelector('[data-testid="container-rows"]')?.textContent ?? "";
    expect(rowsText).toContain("60 %");
    expect(rowsText).toContain("overfull");
    expect(rowsText).not.toContain("100 %");
    expect(document.querySelector('[data-testid="container-rows"]')?.children.length).toBe(2);
  });

  it("shows the empty state on 404 (no dataset loaded)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ detail: "no dataset" }, 404)),
    );

    render(<ContainerList datasetVersion={0} />);
    await flush();

    expect(document.querySelector('[data-testid="empty-state"]')?.textContent).toContain(
      "No dataset loaded",
    );
  });

  it("shows an error state on server failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ detail: "boom" }, 500)),
    );

    render(<ContainerList datasetVersion={0} />);
    await flush();

    expect(document.querySelector('[data-testid="error-state"]')?.textContent).toContain(
      "Could not load containers",
    );
  });
});
