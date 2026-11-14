import { act } from "react";
import { afterEach, describe, expect, it, vi, type Mock } from "vitest";
import { ConfigEditor } from "./ConfigEditor";
import type { PolicyConfigOverride, RoutingConfigOverride } from "../lib/api";
import { click, cleanup, flush, render, setInputValue } from "../test/dom";
import { configFixture } from "../test/fixtures";

function renderEditor(handlers?: {
  onPolicy?: (override: PolicyConfigOverride) => void;
  onRouting?: (override: RoutingConfigOverride) => void;
}) {
  const onPolicyChange: Mock = handlers?.onPolicy ? vi.fn(handlers.onPolicy) : vi.fn();
  const onRoutingChange: Mock = handlers?.onRouting ? vi.fn(handlers.onRouting) : vi.fn();
  render(
    <ConfigEditor
      config={configFixture}
      loading={false}
      error={null}
      policyOverride={{}}
      routingOverride={{}}
      onPolicyChange={onPolicyChange}
      onRoutingChange={onRoutingChange}
    />,
  );
  return { onPolicyChange, onRoutingChange };
}

afterEach(() => {
  cleanup();
});

describe("ConfigEditor", () => {
  it("renders policy and routing fields with defaults and [demo assumption] tags", () => {
    renderEditor();

    expect(document.querySelector('[data-testid="config-select_threshold_pct"]')).not.toBeNull();
    expect(document.querySelector('[data-testid="config-container_volume_litres"]')).not.toBeNull();
    expect(document.querySelector('[data-testid="config-vehicle_count_available"]')).not.toBeNull();
    // Defaults from GET /api/config shown next to inputs.
    expect(document.body.textContent).toContain("default: 80 %");
    expect(document.body.textContent).toContain("default: 1,900 L");
    // Tag counts match assumption_fields (5 listed → 5 tags).
    expect(document.querySelectorAll('[data-testid="assumption-tag"]').length).toBe(5);
  });

  it("keeps the [demo assumption] label visible after editing a value", async () => {
    const { onPolicyChange } = renderEditor();

    const input = document.querySelector<HTMLInputElement>(
      '[data-testid="config-select_threshold_pct"]',
    );
    expect(input).not.toBeNull();
    act(() => {
      setInputValue(input as HTMLInputElement, "90");
    });
    await flush();

    expect(onPolicyChange).toHaveBeenCalledWith({ select_threshold_pct: 90 });
    // Label persists after the edit — overrides never relabel facts (§4.6).
    const rowText = input?.closest("div")?.textContent ?? "";
    expect(rowText).toContain("[demo assumption]");
    expect(rowText).toContain("default: 80 %");
  });

  it("sends nested density overrides per material", async () => {
    const { onRoutingChange } = renderEditor();

    const densityInput = document.querySelector<HTMLInputElement>(
      '[data-testid="config-densities_kg_per_litre.brown"]',
    );
    act(() => {
      setInputValue(densityInput as HTMLInputElement, "0.6");
    });
    await flush();

    expect(onRoutingChange).toHaveBeenCalledWith({
      densities_kg_per_litre: { brown: 0.6 },
    });
  });

  it("reset clears every override back to inherit-default", async () => {
    const { onPolicyChange, onRoutingChange } = renderEditor();

    const input = document.querySelector<HTMLInputElement>(
      '[data-testid="config-select_threshold_pct"]',
    );
    act(() => {
      setInputValue(input as HTMLInputElement, "90");
    });
    await flush();
    onPolicyChange.mockClear();

    await click(document.querySelector('[data-testid="config-reset"]'));
    await flush();

    expect(onPolicyChange).toHaveBeenCalledWith({});
    expect(onRoutingChange).toHaveBeenCalledWith({});
    expect((input as HTMLInputElement).value).toBe("");
  });

  it("falls back to tagging all fields when assumption_fields is missing", () => {
    render(
      <ConfigEditor
        config={{ ...configFixture, assumption_fields: [] }}
        loading={false}
        error={null}
        policyOverride={{}}
        routingOverride={{}}
        onPolicyChange={vi.fn()}
        onRoutingChange={vi.fn()}
      />,
    );
    expect(document.querySelectorAll('[data-testid="assumption-tag"]').length).toBeGreaterThan(10);
  });
});
