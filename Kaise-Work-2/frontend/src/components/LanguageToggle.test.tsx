/** LanguageToggle tests: EN/DE buttons, aria-pressed state, onChange wiring. */
import { afterEach, describe, expect, it, vi } from "vitest";
import { LanguageToggle } from "./LanguageToggle";
import { click, cleanup, render } from "../test/dom";

afterEach(() => {
  cleanup();
});

describe("LanguageToggle", () => {
  it("renders EN and DE buttons with aria-pressed reflecting the active language", () => {
    const view = render(<LanguageToggle lang="en" onChange={() => {}} />);

    const en = view.querySelector('[data-testid="lang-en"]') as HTMLButtonElement;
    const de = view.querySelector('[data-testid="lang-de"]') as HTMLButtonElement;
    expect(en.textContent).toBe("EN");
    expect(de.textContent).toBe("DE");
    expect(en.getAttribute("aria-pressed")).toBe("true");
    expect(de.getAttribute("aria-pressed")).toBe("false");
  });

  it("reports the chosen language via onChange", async () => {
    const onChange = vi.fn();
    const view = render(<LanguageToggle lang="en" onChange={onChange} />);

    await click(view.querySelector('[data-testid="lang-de"]'));
    expect(onChange).toHaveBeenCalledWith("de");

    await click(view.querySelector('[data-testid="lang-en"]'));
    expect(onChange).toHaveBeenCalledWith("en");
  });

  it("marks DE active when lang is de", () => {
    const view = render(<LanguageToggle lang="de" onChange={() => {}} />);
    expect(view.querySelector('[data-testid="lang-de"]')?.getAttribute("aria-pressed")).toBe("true");
    expect(view.querySelector('[data-testid="lang-en"]')?.getAttribute("aria-pressed")).toBe("false");
  });
});
