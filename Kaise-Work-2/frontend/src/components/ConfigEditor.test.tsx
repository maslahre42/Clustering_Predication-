import { act } from "react";
import { afterEach, describe, expect, it, vi, type Mock } from "vitest";
import { ConfigEditor } from "./ConfigEditor";
import type { ConfigDefaults, PolicyConfigOverride, RoutingConfigOverride } from "../lib/api";
import { click, cleanup, flush, render, setInputValue } from "../test/dom";
import { configFixture } from "../test/fixtures";

function renderEditor(handlers?: {
  onPolicy?: (override: PolicyConfigOverride) => void;
  onRouting?: (override: RoutingConfigOverride) => void;
  onRecalculate?: () => void;
}) {
  const onPolicyChange: Mock = handlers?.onPolicy ? vi.fn(handlers.onPolicy) : vi.fn();
  const onRoutingChange: Mock = handlers?.onRouting ? vi.fn(handlers.onRouting) : vi.fn();
  const onRecalculate: Mock = handlers?.onRecalculate ? vi.fn(handlers.onRecalculate) : vi.fn();
  render(
    <ConfigEditor
      config={configFixture}
      lang="en"
      loading={false}
      error={null}
      policyOverride={{}}
      routingOverride={{}}
      onPolicyChange={onPolicyChange}
      onRoutingChange={onRoutingChange}
      onRecalculate={onRecalculate}
    />,
  );
  return { onPolicyChange, onRoutingChange, onRecalculate };
}

afterEach(() => {
  cleanup();
});

describe("ConfigEditor", () => {
  it("renders policy and routing fields with defaults and per-field source tags", () => {
    renderEditor();

    expect(document.querySelector('[data-testid="config-select_threshold_pct"]')).not.toBeNull();
    expect(document.querySelector('[data-testid="config-container_volume_litres"]')).not.toBeNull();
    expect(document.querySelector('[data-testid="config-vehicle_count_available"]')).not.toBeNull();
    // Defaults from GET /api/config shown next to inputs (v3 values).
    expect(document.body.textContent).toContain("default: 80 %");
    expect(document.body.textContent).toContain("default: 3,000 L");
    // v3 source tags: 19 [demo assumption] + 8 [representative] — never mixed.
    expect(document.querySelectorAll('[data-testid="assumption-tag"]').length).toBe(19);
    expect(document.querySelectorAll('[data-testid="representative-tag"]').length).toBe(8);
    // Highlighted key-parameter group + v3 fields exist.
    expect(document.querySelector('[data-testid="config-travel_time_mode"]')).not.toBeNull();
    expect(document.querySelector('[data-testid="config-cost_per_truck_day_eur"]')).not.toBeNull();
    expect(document.querySelector('[data-testid="config-geography_seed"]')).not.toBeNull();
    expect(document.body.textContent).toContain("Key parameters");
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

  it("fails safe: a missing sources map labels every field [demo assumption]", () => {
    render(
      <ConfigEditor
        config={{ ...configFixture, sources: {} } as unknown as ConfigDefaults}
        loading={false}
        error={null}
        lang="en"
        policyOverride={{}}
        routingOverride={{}}
        onPolicyChange={vi.fn()}
        onRoutingChange={vi.fn()}
      />,
    );
    // All 27 rendered field rows (3 policy + 1 travel mode + 13 key + 10 other)
    // degrade to [demo assumption] — never silently upgraded to facts (§5.3).
    expect(document.querySelectorAll('[data-testid="assumption-tag"]').length).toBe(27);
    expect(document.querySelectorAll('[data-testid="representative-tag"]').length).toBe(0);
  });

  it("Recalculate button re-runs the auto-computed views via onRecalculate", async () => {
    const { onRecalculate } = renderEditor({
      onRecalculate: () => {},
    });

    await click(document.querySelector('[data-testid="config-recalculate"]'));
    await flush();

    expect(onRecalculate).toHaveBeenCalledTimes(1);
    // Reset still present alongside Recalculate.
    expect(document.querySelector('[data-testid="config-reset"]')).not.toBeNull();
  });
});
