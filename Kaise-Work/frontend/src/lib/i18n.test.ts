import { describe, expect, it } from "vitest";
import { ALL_TRANSLATION_KEYS, DICTS, t, tf, type Lang } from "./i18n";

const LANGS: readonly Lang[] = ["en", "de"];

describe("i18n EN/DE key parity (file-header promise)", () => {
  it("en and de expose exactly the same key sets", () => {
    const enKeys = Object.keys(DICTS.en).sort();
    const deKeys = Object.keys(DICTS.de).sort();
    expect(deKeys).toEqual(enKeys);
    // ALL_TRANSLATION_KEYS mirrors the en dictionary.
    expect([...ALL_TRANSLATION_KEYS].sort()).toEqual(enKeys);
  });

  it("every translation is a non-empty string in both languages", () => {
    for (const lang of LANGS) {
      for (const [key, value] of Object.entries(DICTS[lang])) {
        expect(value, `${lang} "${key}" is empty`).not.toBe("");
      }
    }
  });

  it("t and tf substitute placeholders in both languages", () => {
    expect(t("en", "legend.brown")).toBe("Brown glass");
    expect(t("de", "legend.brown")).toBe("Braunglas");

    const en = tf("en", "overview.recommendation.toEmpty", { n: 458 });
    const de = tf("de", "overview.recommendation.toEmpty", { n: 458 });
    expect(en).toContain("458");
    expect(de).toContain("458");
    expect(en).not.toContain("{n}");
    expect(de).not.toContain("{n}");
  });
});
