import { useState } from "react";
import { ApiError, loadDemoDataset, type DatasetSummary } from "../lib/api";
import { t, type Lang } from "../lib/i18n";
import { ErrorState, LoadingState } from "./states";

/**
 * "Load demo data" button (§5.1 POST /api/datasets/demo): loads the
 * server-side demo CSV (path fixed server-side). The response `source_name`
 * carries a `demo:` prefix (§5.2.2) — App renders the synthetic-data banner
 * from it. Loading and error states are translated (EN/DE).
 */
export function DemoLoadButton({
  lang,
  onLoaded,
}: {
  lang: Lang;
  onLoaded: (summary: DatasetSummary) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleClick() {
    setBusy(true);
    setError(null);
    try {
      const summary = await loadDemoDataset();
      onLoaded(summary);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2" data-testid="demo-load">
      <button
        type="button"
        onClick={() => void handleClick()}
        disabled={busy}
        className="rounded bg-emerald-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-800 disabled:opacity-50"
        data-testid="demo-load-button"
      >
        {busy ? `${t(lang, "demo.loading")}…` : t(lang, "demo.button")}
      </button>
      {busy ? <LoadingState label={t(lang, "demo.loading")} /> : null}
      {error !== null && !busy ? (
        <ErrorState label={t(lang, "demo.error")} hint={error} />
      ) : null}
    </div>
  );
}
