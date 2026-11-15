/** TechDetails tests: native <details> collapse — children stay in the DOM. */
import { afterEach, describe, expect, it } from "vitest";
import { TechDetails } from "./TechDetails";
import { click, cleanup, render } from "../test/dom";

afterEach(() => {
  cleanup();
});

describe("TechDetails", () => {
  it("renders the label with children present but collapsed by default", () => {
    const view = render(
      <TechDetails label="Technical details">
        <p>status: feasible</p>
      </TechDetails>,
    );

    const details = view.querySelector('[data-testid="tech-details"]');
    expect(details?.tagName).toBe("DETAILS");
    expect((details as HTMLDetailsElement).open).toBe(false);
    expect(view.querySelector("summary")?.textContent).toBe("Technical details");
    // Children stay in the DOM when collapsed (accessible + testable).
    expect(details?.textContent).toContain("status: feasible");
  });

  it("expands on click and exposes the content", async () => {
    const view = render(
      <TechDetails label="Technical details" testid="comparison-tech-details">
        <p>Distances: straight-line — NOT road distance</p>
      </TechDetails>,
    );

    await click(view.querySelector("summary"));
    const details = view.querySelector('[data-testid="comparison-tech-details"]') as HTMLDetailsElement;
    expect(details.open).toBe(true);
    expect(details.textContent).toContain("NOT road distance");
  });
});
