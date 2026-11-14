/**
 * Minimal EN/DE translation file (M11+ jury-usability pass). Scope per task:
 * Overview + "Today's recommendation" views are translated; other panels keep
 * their generated English insight titles for now. Keys are typed: `de` must
 * implement every `en` key (checked by i18n.test.ts as well).
 *
 * Language rules baked into the strings (task requirement):
 * - historical shares are shares of *readings* — never "emptyings"
 *   (the data has no collection events, docs/contracts.md §5.2.2);
 * - distances are straight-line estimates, never road distance;
 * - demo/synthetic inputs stay visibly labelled.
 */

export type Lang = "en" | "de";

const en = {
  "nav.overview": "Overview",
  "nav.data": "Data & upload",
  "nav.containers": "Containers",
  "nav.forecast": "Forecast & candidates",
  "nav.route": "Route plan",
  "nav.config": "Configuration",

  "legend.title": "Glass colours",

  "overview.headline":
    "Know which glass containers need emptying — and plan the trucks accordingly",
  "overview.problem":
    "Container glass is often emptied on fixed schedules without knowing how full each container really is. This prototype forecasts fill levels from real sensor readings and proposes feasible, optimised collection routes — every recommendation comes with an explanation.",

  "overview.keynum.readings.title": "Readings with full containers",
  "overview.keynum.readings.note":
    "Share of historical readings at or above {thr} % fill (threshold: demo assumption) — these are sensor readings: the data contains no collection events.",
  "overview.keynum.containers.title": "Containers expected to need emptying",
  "overview.keynum.containers.note":
    "Model prediction for {date}: selected by the recommendation below — not a measured fact.",
  "overview.keynum.distance.title": "Planned distance: sweep-all vs optimised",
  "overview.keynum.distance.fixed": "Sweep all stops",
  "overview.keynum.distance.optimised": "Optimised",
  "overview.keynum.distance.savings":
    "Derived saving (total gain ÷ sweep-all distance): {pct}",

  "overview.how.title": "How it works",
  "overview.how.step1": "Upload fill-level readings",
  "overview.how.step2": "Forecast how full each container will be",
  "overview.how.step3": "Select containers that need emptying — with a reason",
  "overview.how.step4": "Compute feasible routes and explain every stop",

  "overview.recommendation.title": "Today's recommendation",
  "overview.recommendation.asof": "as of {date} (last reading date)",
  "overview.recommendation.horizon":
    "expected fill in {days} days — prediction, not measurement",
  "overview.recommendation.toEmpty": "{n} containers to empty",
  "overview.recommendation.canWait": "{n} can wait",
  "overview.recommendation.noForecast": "{n} have no forecast",
  "overview.recommendation.examples": "Top examples",
  "overview.recommendation.caption":
    "What this shows: which containers are recommended for the next collection round and why. Why it matters: overfull containers annoy residents — this turns readings into an explainable work list.",

  "overview.beforeafter.title": "From sweeping everything to optimised routes",
  "overview.beforeafter.caption":
    "What this shows: three scenarios on the same dataset — the status-quo sweep over every stop, a sweep over only the recommended stops, and optimised routing. Why it matters: distance per kg collected compares the scenarios fairly (they serve different numbers of stops); raw distances do not. Distances are straight-line estimates, not road kilometres.",
  "overview.compare.step1.title": "Status quo: sweep every stop",
  "overview.compare.step1.short": "Sweep all stops",
  "overview.compare.step2.title": "Selection effect: sweep only the recommended stops",
  "overview.compare.step2.short": "Sweep selected stops",
  "overview.compare.step3.title": "Optimised routes (OR-Tools)",
  "overview.compare.step3.short": "Optimised (OR-Tools)",
  "overview.compare.step3.medianSuffix": "median of {runs} solves",
  "overview.compare.selectionGain": "Selection gain (sweep-all → selection sweep): {gain}",
  "overview.compare.selectionGainNegative":
    "Negative = the selection sweep covered MORE distance than the sweep-all run — selection did not pay off for distance here.",
  "overview.compare.routingGain": "Routing gain (selection sweep → optimised): {gain}",
  "overview.compare.totalGain": "Total distance gain (status quo → optimised): {gain}",
  "overview.compare.gainUnavailable":
    "Gain not available for this run — no usable optimised solution to compare against.",
  "overview.compare.perKgNote":
    "Distance per kg collected is the like-for-like comparison across these scenarios (they serve different numbers of stops); raw distances are not comparable. Distances are straight-line estimates, not road kilometres.",
  "overview.compare.savings": "Derived saving share (total gain ÷ status-quo distance): {pct}",
  "overview.compare.determinism.identical":
    "Optimised result deterministic: identical distance across {runs} solves ({median}).",
  "overview.compare.determinism.medianOfRuns":
    "Optimised distance varied across {runs} solves (wall-clock solver variance): median {median}, range {min}–{max}. The median is shown above.",
  "col.distance": "Distance",
  "col.distancePerKg": "Distance per kg",
  "col.duration": "Duration",
  "col.trucks": "Trucks needed",
  "col.stopsServed": "Stops served",
  "col.unserved": "Unserved",
  "col.volume": "Volume collected",
  "col.weight": "Weight collected",
  "unit.containers": "containers",
  "unit.vehicles": "vehicles",

  "overview.calmnote":
    "Please note: locations, vehicles and densities in this prototype are demo assumptions. Distances are straight-line estimates — not real road distances.",

  "demo.button": "Load demo data",
  "demo.loading": "Loading demo data",
  "demo.error": "Could not load demo data",

  "overview.reason.at_or_above_threshold":
    "Predicted at or above the emptying threshold — recommend emptying",
  "overview.reason.overfull_state":
    "Last reading was overfull — always recommended",
  "overview.reason.below_threshold": "Still room left — can wait",
  "overview.reason.no_forecast": "No forecast possible — check manually",

  "overview.state.loading": "Loading overview",
  "overview.state.noDataset":
    "No dataset loaded yet — upload a CSV or load the demo data below.",
  "overview.state.summaryError": "Could not load the dataset summary",
  "overview.state.recommendationLoading": "Computing recommendation",
  "overview.state.recommendationError": "Could not compute the recommendation",
  "overview.state.noAsOf": "No last reading date available — recommendation skipped.",
  "overview.state.noFillStats":
    "Fill-level shares are not available for this dataset summary.",
  "overview.state.comparisonLoading": "Computing fixed-vs-optimised comparison",
  "overview.state.comparisonError": "Could not compute the comparison",
  "overview.state.comparisonNoDataset":
    "No dataset loaded — the comparison becomes available after loading data.",
  "overview.tech.assumptions": "Labelled assumptions returned by the API",

  "techdetails.label": "Technical details",

  "legend.brown": "Brown glass",
  "legend.green": "Green glass",
  "legend.white": "White glass",
} as const;

export type TranslationKey = keyof typeof en;

const de: Record<TranslationKey, string> = {
  "nav.overview": "Übersicht",
  "nav.data": "Daten & Upload",
  "nav.containers": "Behälter",
  "nav.forecast": "Prognose & Kandidaten",
  "nav.route": "Routenplan",
  "nav.config": "Konfiguration",

  "legend.title": "Glasfarben",

  "overview.headline":
    "Wissen, welche Glasbehälter geleert werden müssen — und die Fahrzeuge entsprechend planen",
  "overview.problem":
    "Container-Glas wird oft nach festen Zeitplänen geleert, ohne dass bekannt ist, wie voll jeder Behälter wirklich ist. Dieser Prototyp prognostiziert Füllstände aus echten Sensordaten und schlägt machbare, optimierte Sammelrouten vor — jede Empfehlung ist mit einer Begründung versehen.",

  "overview.keynum.readings.title": "Messungen mit vollem Behälter",
  "overview.keynum.readings.note":
    "Anteil der historischen Messungen mit Füllstand ≥ {thr} % (Schwelle: Demo-Annahme) — das sind Sensor-Messungen: Der Datensatz enthält keine Sammel-Ereignisse.",
  "overview.keynum.containers.title": "Behälter, die voraussichtlich zu leeren sind",
  "overview.keynum.containers.note":
    "Modellprognose für {date}: von der Empfehlung unten ausgewählt — kein gemessener Fakt.",
  "overview.keynum.distance.title": "Geplante Strecke: Alles-Sweep vs. optimiert",
  "overview.keynum.distance.fixed": "Alle Stopps abfahren",
  "overview.keynum.distance.optimised": "Optimiert",
  "overview.keynum.distance.savings":
    "Abgeleitete Ersparnis (Gesamtgewinn ÷ Sweep-alle-Stopp-Strecke): {pct}",

  "overview.how.title": "So funktioniert es",
  "overview.how.step1": "Füllstands-Messungen hochladen",
  "overview.how.step2": "Prognostizieren, wie voll jeder Behälter sein wird",
  "overview.how.step3": "Zu leerende Behälter auswählen — mit Begründung",
  "overview.how.step4": "Machbare Routen berechnen und jeden Stopp erklären",

  "overview.recommendation.title": "Empfehlung für heute",
  "overview.recommendation.asof": "Stand: {date} (letztes Messdatum)",
  "overview.recommendation.horizon":
    "erwarteter Füllstand in {days} Tagen — Prognose, nicht Messung",
  "overview.recommendation.toEmpty": "{n} Behälter leeren",
  "overview.recommendation.canWait": "{n} kann warten",
  "overview.recommendation.noForecast": "{n} ohne Prognose",
  "overview.recommendation.examples": "Top-Beispiele",
  "overview.recommendation.caption":
    "Was das zeigt: welche Behälter für die nächste Sammelrunde empfohlen werden und warum. Warum das zählt: übervolle Behälter ärgern Anwohner — daraus wird eine begründete Arbeitsliste.",

  "overview.beforeafter.title": "Vom Alles-Abfahren zur optimierten Route",
  "overview.beforeafter.caption":
    "Was das zeigt: drei Szenarien auf demselben Datensatz — der Status-quo-Sweep über alle Stopps, ein Sweep nur über die empfohlenen Stopps und optimierte Routen. Warum das zählt: Strecke pro kg vergleich die Szenarien fair (sie bedienen unterschiedlich viele Stopps); rohe Strecken sind nicht vergleichbar. Entfernungen sind Luftlinien-Schätzungen, keine Straßen-Kilometer.",
  "overview.compare.step1.title": "Status quo: alle Stopps abfahren",
  "overview.compare.step1.short": "Alle Stopps",
  "overview.compare.step2.title": "Auswahl-Effekt: nur die empfohlenen Stopps abfahren",
  "overview.compare.step2.short": "Ausgewählte Stopps",
  "overview.compare.step3.title": "Optimierte Routen (OR-Tools)",
  "overview.compare.step3.short": "Optimiert (OR-Tools)",
  "overview.compare.step3.medianSuffix": "Median aus {runs} Läufen",
  "overview.compare.selectionGain": "Auswahl-Gewinn (Sweep-alle → Auswahl-Sweep): {gain}",
  "overview.compare.selectionGainNegative":
    "Negativ = der Auswahl-Sweep hatte eine GRÖSSERE Strecke als der Sweep-alle-Lauf — die Auswahl hat sich hier (bei der Strecke) nicht gelohnt.",
  "overview.compare.routingGain": "Routing-Gewinn (Auswahl-Sweep → optimiert): {gain}",
  "overview.compare.totalGain": "Gesamt-Strecken-Gewinn (Status quo → optimiert): {gain}",
  "overview.compare.gainUnavailable":
    "Gewinn für diesen Lauf nicht verfügbar — keine nutzbare optimierte Lösung zum Vergleich.",
  "overview.compare.perKgNote":
    "Strecke pro kg ist der faire Vergleich zwischen diesen Szenarien (sie bedienen unterschiedlich viele Stopps); rohe Strecken sind nicht vergleichbar. Entfernungen sind Luftlinien-Schätzungen, keine Straßen-Kilometer.",
  "overview.compare.savings": "Abgeleitete Ersparnis (Gesamtgewinn ÷ Status-quo-Strecke): {pct}",
  "overview.compare.determinism.identical":
    "Optimiertes Ergebnis deterministisch: identische Strecke über {runs} Läufe ({median}).",
  "overview.compare.determinism.medianOfRuns":
    "Optimierte Strecke variierte über {runs} Läufe (Wall-Clock-Solver-Varianz): Median {median}, Spanne {min}–{max}. Oben ist der Median gezeigt.",
  "col.distance": "Strecke",
  "col.distancePerKg": "Strecke pro kg",
  "col.duration": "Dauer",
  "col.trucks": "Fahrzeuge benötigt",
  "col.stopsServed": "Stopps bedient",
  "col.unserved": "Nicht bedient",
  "col.volume": "Volumen gesammelt",
  "col.weight": "Gewicht gesammelt",
  "unit.containers": "Behälter",
  "unit.vehicles": "Fahrzeuge",

  "overview.calmnote":
    "Hinweis: Standorte, Fahrzeuge und Dichten in diesem Prototyp sind Demo-Annahmen. Entfernungen sind Luftlinien-Schätzungen — keine echten Straßen-Kilometer.",

  "demo.button": "Demo-Daten laden",
  "demo.loading": "Demo-Daten werden geladen",
  "demo.error": "Demo-Daten konnten nicht geladen werden",

  "overview.reason.at_or_above_threshold":
    "Voraussichtlich auf oder über der Leeren-Schwelle — Leeren empfohlen",
  "overview.reason.overfull_state":
    "Letzte Messung war übervoll — immer empfohlen",
  "overview.reason.below_threshold": "Noch Platz — kann warten",
  "overview.reason.no_forecast": "Keine Prognose möglich — bitte prüfen",

  "overview.state.loading": "Übersicht wird geladen",
  "overview.state.noDataset":
    "Noch keine Daten geladen — bitte CSV hochladen oder unten die Demo-Daten laden.",
  "overview.state.summaryError": "Datensatz-Übersicht konnte nicht geladen werden",
  "overview.state.recommendationLoading": "Empfehlung wird berechnet",
  "overview.state.recommendationError": "Empfehlung konnte nicht berechnet werden",
  "overview.state.noAsOf": "Kein letztes Messdatum vorhanden — Empfehlung übersprungen.",
  "overview.state.noFillStats":
    "Füllstands-Anteile sind für diese Datensatz-Übersicht nicht verfügbar.",
  "overview.state.comparisonLoading": "Vergleich fest-vs-optimiert wird berechnet",
  "overview.state.comparisonError": "Vergleich konnte nicht berechnet werden",
  "overview.state.comparisonNoDataset":
    "Keine Daten geladen — der Vergleich ist nach dem Laden verfügbar.",
  "overview.tech.assumptions": "Von der API zurückgegebene, gelabelte Annahmen",

  "techdetails.label": "Technische Details",

  "legend.brown": "Braunglas",
  "legend.green": "Grünglas",
  "legend.white": "Weißglas",
};

const DICTS: Record<Lang, Record<TranslationKey, string>> = { en, de };
export { DICTS };

/** Translate a key. Falls back to the key itself if a dict entry is missing. */
export function t(lang: Lang, key: TranslationKey): string {
  return DICTS[lang][key] ?? key;
}

/** Translate with {placeholder} substitution. */
export function tf(
  lang: Lang,
  key: TranslationKey,
  params: Record<string, string | number>,
): string {
  let text: string = DICTS[lang][key] ?? key;
  for (const [name, value] of Object.entries(params)) {
    text = text.replaceAll(`{${name}}`, String(value));
  }
  return text;
}

export const ALL_TRANSLATION_KEYS: readonly TranslationKey[] = Object.keys(en) as readonly TranslationKey[];
