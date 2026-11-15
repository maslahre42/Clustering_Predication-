import { describe, expect, it } from "vitest";
import {
  formatInt,
  formatKg,
  formatLitres,
  formatMetres,
  formatMinutes,
  formatPct,
  formatStopKey,
  provenanceLabel,
  reasonLabel,
} from "./format";

describe("format helpers (explicit units)", () => {
  it("formats metres with a km aid only at >= 1000 m", () => {
    expect(formatMetres(18400)).toBe("18,400 m (18.4 km)");
    expect(formatMetres(500)).toBe("500 m");
    expect(formatMetres(null)).toBe("— m");
  });

  it("formats minutes, litres, kg and ints with units", () => {
    expect(formatMinutes(95)).toBe("95 min");
    expect(formatLitres(1200)).toBe("1,200 L");
    expect(formatKg(600)).toBe("600 kg");
    expect(formatInt(11701, "rows")).toBe("11,701 rows");
    expect(formatInt(undefined, "rows")).toBe("— rows");
  });

  it("formats percent with 1 decimal", () => {
    expect(formatPct(92)).toBe("92.0 %");
    expect(formatPct(60, 0)).toBe("60 %");
    expect(formatPct(null)).toBe("— %");
  });

  it("formats flat unserved entries (backend UnservedStopResponse shape)", () => {
    expect(formatStopKey({ location_id: "loc-3", material_type: "white" })).toBe("loc-3 · white");
  });

  it("labels straight-line provenance as NOT road distance", () => {
    expect(provenanceLabel("haversine_straight_line_derived")).toContain("NOT road distance");
    expect(provenanceLabel("external")).toContain("external matrix");
  });

  it("humanises reason codes", () => {
    expect(reasonLabel("at_or_above_threshold")).toBe("at or above threshold");
  });
});
