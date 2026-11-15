/** GlassLegend tests: title + one swatch per material type (EN/DE). */
import { afterEach, describe, expect, it } from "vitest";
import { GlassLegend } from "./GlassLegend";
import { MATERIAL_TYPES } from "../lib/api";
import { cleanup, render } from "../test/dom";

afterEach(() => {
  cleanup();
});

describe("GlassLegend", () => {
  it("renders a title and one colour swatch per material type in EN", () => {
    const view = render(<GlassLegend lang="en" />);

    expect(view.querySelector('[data-testid="glass-legend"]')?.textContent).toContain("Glass colours");
    expect(view.querySelectorAll("span[aria-hidden]").length).toBe(MATERIAL_TYPES.length);
    const text = view.querySelector('[data-testid="glass-legend"]')?.textContent ?? "";
    expect(text).toContain("Brown glass");
    expect(text).toContain("Green glass");
    expect(text).toContain("White glass");
  });

  it("renders the German labels in DE", () => {
    const view = render(<GlassLegend lang="de" />);
    const text = view.querySelector('[data-testid="glass-legend"]')?.textContent ?? "";
    expect(text).toContain("Glasfarben");
    expect(text).toContain("Braunglas");
    expect(text).toContain("Grünglas");
    expect(text).toContain("Weißglas");
  });
});
