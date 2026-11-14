import { useEffect, useState } from "react";
import {
  ApiError,
  fetchConfig,
  fetchSummary,
  type ConfigDefaults,
  type DatasetSummary,
  type PolicyConfigOverride,
  type RouteResponse,
  type RoutingConfigOverride,
} from "./lib/api";
import { fetchHealth, type Health } from "./lib/health";
import { t, type Lang, type TranslationKey } from "./lib/i18n";
import { CandidatesPanel } from "./components/CandidatesPanel";
import { ConfigEditor } from "./components/ConfigEditor";
import { ContainerList } from "./components/ContainerList";
import { KpiOverview } from "./components/KpiOverview";
import { LanguageToggle } from "./components/LanguageToggle";
import { Overview } from "./components/Overview";
import { RoutePanel } from "./components/RoutePanel";
import { SyntheticDataBanner } from "./components/SyntheticDataBanner";
import { UploadPanel } from "./components/UploadPanel";
import { ErrorBoundary } from "./components/ErrorBoundary";

/**
 * Operator dashboard (M11 + jury-usability pass). Tab navigation with the
 * plain-language Overview first; ALL panels stay mounted (hidden via the
 * `hidden` attribute) so state is kept and cross-panel flows keep working.
 * Demo geography/values are always visibly labelled; observed vs predicted vs
 * [demo assumption] is never mixed.
 */
type TabId = "overview" | "data" | "containers" | "forecast" | "route" | "config";

const TABS: ReadonlyArray<{ id: TabId; labelKey: TranslationKey; testid: string }> = [
  { id: "overview", labelKey: "nav.overview", testid: "nav-overview" },
  { id: "data", labelKey: "nav.data", testid: "nav-data" },
  { id: "containers", labelKey: "nav.containers", testid: "nav-containers" },
  { id: "forecast", labelKey: "nav.forecast", testid: "nav-forecast" },
  { id: "route", labelKey: "nav.route", testid: "nav-route" },
  { id: "config", labelKey: "nav.config", testid: "nav-config" },
];

export default function App() {
  // UI language (Overview is translated; technical panels stay English).
  const [lang, setLang] = useState<Lang>("en");
  const [activeTab, setActiveTab] = useState<TabId>("overview");

  // Liveness (M0 convention, asserted by App.test.tsx).
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  // Active dataset.
  const [summary, setSummary] = useState<DatasetSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [datasetVersion, setDatasetVersion] = useState(0);

  // Config defaults + user overrides (lifted to candidates/route panels).
  const [config, setConfig] = useState<ConfigDefaults | null>(null);
  const [configLoading, setConfigLoading] = useState(true);
  const [configError, setConfigError] = useState<string | null>(null);
  const [policyOverride, setPolicyOverride] = useState<PolicyConfigOverride>({});
  const [routingOverride, setRoutingOverride] = useState<RoutingConfigOverride>({});

  // Synthetic/demo markers from the latest route response (§5.3).
  const [routeAssumptions, setRouteAssumptions] = useState<string[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchHealth()
      .then((payload) => {
        if (!cancelled) setHealth(payload);
      })
      .catch(() => {
        if (!cancelled) setHealthError("API unreachable");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setSummaryLoading(true);
    setSummaryError(null);
    fetchSummary()
      .then((payload) => {
        if (!cancelled) setSummary(payload);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        // 404 = no dataset yet → empty state, not an error (§5.3).
        if (!(err instanceof ApiError && err.status === 404)) {
          setSummaryError(err instanceof ApiError ? err.message : String(err));
        }
        setSummary(null);
      })
      .finally(() => {
        if (!cancelled) setSummaryLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [datasetVersion]);

  useEffect(() => {
    let cancelled = false;
    setConfigLoading(true);
    fetchConfig()
      .then((payload) => {
        if (!cancelled) setConfig(payload);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setConfigError(err instanceof ApiError ? err.message : String(err));
        }
      })
      .finally(() => {
        if (!cancelled) setConfigLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function handleUploaded(uploaded: DatasetSummary) {
    setSummary(uploaded);
    setDatasetVersion((v) => v + 1);
  }

  function handleRoute(response: RouteResponse) {
    setRouteAssumptions(Array.isArray(response.assumptions) ? response.assumptions : []);
  }

  // Demo data in play: route assumptions returned, or a demo-prefixed dataset
  // (POST /api/datasets/demo labels source_name with a `demo:` prefix, §5.2.2).
  // Guarded: mocked/malformed summaries must not crash on missing source_name.
  const demoDataset =
    typeof summary?.source_name === "string" && summary.source_name.startsWith("demo:");
  const demoInPlay = routeAssumptions !== null || demoDataset;

  return (
    <main className="mx-auto min-h-screen max-w-7xl bg-slate-50 p-6 lg:p-8">
      <header className="mb-4">
        <h1 className="text-2xl font-bold text-slate-900">WasteRouting.AI</h1>
        <p className="mt-1 text-sm text-slate-500">
          Glass-waste collection forecasting &amp; routing (prototype) — observed data, model
          predictions and [demo assumption] values are always labelled.
        </p>
        <p className="mt-1 text-sm text-slate-700" data-testid="health">
          API health:{" "}
          {healthError !== null ? (
            <span className="font-semibold text-red-600">{healthError}</span>
          ) : health !== null ? (
            <span className="font-semibold text-green-700">{health.status}</span>
          ) : (
            "checking…"
          )}
        </p>
      </header>

      {demoInPlay ? (
        <div className="mb-4">
          <SyntheticDataBanner assumptions={routeAssumptions ?? []} />
        </div>
      ) : null}

      {/* Tab navigation — Overview first for non-technical users */}
      <nav
        className="mb-4 flex flex-wrap items-center gap-1 rounded-lg border border-slate-200 bg-white p-1 shadow-sm"
        aria-label="Main views"
        data-testid="main-nav"
      >
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            aria-current={activeTab === tab.id ? "page" : undefined}
            className={
              activeTab === tab.id
                ? "rounded bg-sky-700 px-3 py-1.5 text-sm font-semibold text-white"
                : "rounded px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100"
            }
            data-testid={tab.testid}
          >
            {t(lang, tab.labelKey)}
          </button>
        ))}
        <div className="ml-auto pr-1">
          <LanguageToggle lang={lang} onChange={setLang} />
        </div>
      </nav>

      {/* One boundary per main view: a render error degrades that view to a
          visible retryable message — never a blank dashboard (M11).
          Every panel stays mounted; inactive tabs are merely hidden. */}
      <div className="space-y-4">
        <div hidden={activeTab !== "overview"}>
          <ErrorBoundary label="Overview">
            <Overview
              lang={lang}
              summary={summary}
              summaryLoading={summaryLoading}
              summaryError={summaryError}
              datasetVersion={datasetVersion}
              onDemoLoaded={handleUploaded}
            />
          </ErrorBoundary>
        </div>

        <div hidden={activeTab !== "data"} className="grid gap-4 xl:grid-cols-2">
          <ErrorBoundary label="Upload">
            <UploadPanel onUploaded={handleUploaded} />
          </ErrorBoundary>
          <ErrorBoundary label="Dataset overview">
            <KpiOverview summary={summary} loading={summaryLoading} error={summaryError} />
          </ErrorBoundary>
        </div>

        <div hidden={activeTab !== "containers"}>
          <ErrorBoundary label="Containers">
            <ContainerList datasetVersion={datasetVersion} />
          </ErrorBoundary>
        </div>

        <div hidden={activeTab !== "forecast"}>
          <ErrorBoundary label="Forecast & candidates">
            <CandidatesPanel
              defaultAsOf={summary?.date_max ?? null}
              policyOverride={policyOverride}
            />
          </ErrorBoundary>
        </div>

        <div hidden={activeTab !== "route"}>
          <ErrorBoundary label="Route proposal">
            <RoutePanel
              defaultAsOf={summary?.date_max ?? null}
              policyOverride={policyOverride}
              routingOverride={routingOverride}
              onRoute={handleRoute}
            />
          </ErrorBoundary>
        </div>

        <div hidden={activeTab !== "config"}>
          <ErrorBoundary label="Demo config">
            <ConfigEditor
              config={config}
              loading={configLoading}
              error={configError}
              policyOverride={policyOverride}
              routingOverride={routingOverride}
              onPolicyChange={setPolicyOverride}
              onRoutingChange={setRoutingOverride}
            />
          </ErrorBoundary>
        </div>
      </div>

      <footer className="mt-6 text-xs text-slate-400">
        Prototype limitation: the API keeps one active dataset in memory; uploads replace it
        (docs/contracts.md §5). Coordinates and fleet values are synthetic until the host supplies
        real ones.
      </footer>
    </main>
  );
}
