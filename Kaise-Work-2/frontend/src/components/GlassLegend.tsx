import { MATERIAL_TYPES, type MaterialType } from "../lib/api";
import { t, type Lang, type TranslationKey } from "../lib/i18n";

const SWATCH: Record<MaterialType, string> = {
  brown: "bg-amber-800",
  green: "bg-emerald-600",
  white: "bg-slate-400",
};

/** Glass-colour legend (brown/green/white — §1.1 observed material values). */
export function GlassLegend({ lang }: { lang: Lang }) {
  return (
    <div
      className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-600"
      data-testid="glass-legend"
    >
      <span className="font-medium text-slate-500">{t(lang, "legend.title")}:</span>
      {MATERIAL_TYPES.map((material) => (
        <span key={material} className="inline-flex items-center gap-1">
          <span className={`inline-block h-2.5 w-2.5 rounded-full ${SWATCH[material]}`} aria-hidden />
          {t(lang, `legend.${material}` as TranslationKey)}
        </span>
      ))}
    </div>
  );
}
