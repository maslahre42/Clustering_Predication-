/**
 * Minimal jsdom render helpers (no @testing-library dependency): createRoot +
 * act, matching the existing App.test.tsx convention.
 */
import { act } from "react";
import type { ReactElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { expect } from "vitest";

(globalThis as unknown as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

const roots: Root[] = [];

export function render(ui: ReactElement): HTMLElement {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  roots.push(root);
  act(() => {
    root.render(ui);
  });
  return container;
}

/** Flush pending promises and React state updates (e.g. after fetch resolves). */
export async function flush(): Promise<void> {
  await act(async () => {});
}

/** Fire a native click on an element (bubbling, so React onClick handlers run). */
export async function click(element: Element | null): Promise<void> {
  expect(element).not.toBeNull();
  await act(async () => {
    element?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
  await flush();
}

/** Set a controlled input value via the native setter so React onChange fires. */
export function setInputValue(input: Element, value: string): void {
  if (!(input instanceof HTMLInputElement)) throw new TypeError("not an input");
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  setter?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

/** Set a controlled <select> value via the native setter so React onChange fires. */
export function setSelectValue(select: Element, value: string): void {
  if (!(select instanceof HTMLSelectElement)) throw new TypeError("not a select");
  const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")?.set;
  setter?.call(select, value);
  select.dispatchEvent(new Event("change", { bubbles: true }));
}

export function cleanup(): void {
  act(() => {
    for (const root of roots.splice(0)) {
      root.unmount();
    }
  });
  document.body.innerHTML = "";
}

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
