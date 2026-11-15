import type { Lang } from "../lib/i18n";

/**
 * EN/DE language switch (M11 jury-usability pass). Only the Overview page is
 * translated today (see src/lib/i18n.ts scope note); technical panels stay
 * English. aria-pressed keeps the active language explicit.
 */
export function LanguageToggle({
  lang,
  onChange,
}: {
  lang: Lang;
  onChange: (lang: Lang) => void;
}) {
  return (
    <div
      className="inline-flex overflow-hidden rounded border border-slate-300 bg-white"
      data-testid="lang-toggle"
      role="group"
      aria-label="Language / Sprache"
    >
      {(["en", "de"] as const).map((code) => (
        <button
          key={code}
          type="button"
          onClick={() => onChange(code)}
          aria-pressed={lang === code}
          className={
            lang === code
              ? "bg-sky-700 px-2.5 py-1 text-xs font-semibold text-white"
              : "px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100"
          }
          data-testid={`lang-${code}`}
        >
          {code === "en" ? "EN" : "DE"}
        </button>
      ))}
    </div>
  );
}
