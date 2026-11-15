<script setup lang="ts">
import type { ProposalDataset, DataIssue } from '~/shared/api/contracts/comparison';
import { createScenarioComparison } from '../state/createScenarioComparison';
import { createProposalDataset } from '../state/createProposalDataset';
import type { ProposalSettings } from '~/shared/api/contracts/proposal';
import { downloadCsv } from '~/shared/browser/download';
import { useCollectionProposal } from '../composables/useCollectionProposal';
import { REASON_LABELS, formatHours, proposalCsv, proposalSummary } from '../domain/proposal';
import { DEFAULT_PROPOSAL_SETTINGS } from '../domain/settings';
import { createProposalSettings } from '../state/createProposalSettings';

const { asOf, clusters } = useWorkspaceData();
const { view } = useWorkspaceNavigation();
const plan = useCollectionPlan();
// Applied settings survive switching between workspace modules.
const stored = useState<ProposalSettings>('proposal-settings', () => ({ ...DEFAULT_PROPOSAL_SETTINGS }));
const dataset = useState<ProposalDataset | null>('proposal-dataset', () => null);
const upload = createProposalDataset(dataset);
watch(dataset, () => plan.clearPlan(), { flush: 'sync' });
const settings = createProposalSettings(stored.value, DEFAULT_PROPOSAL_SETTINGS);
const { data, error, status, refresh, ready, problem } = useCollectionProposal(asOf, stored, dataset);

const scenarioContext = computed(() => JSON.stringify([asOf.value,dataset.value]));
const scenarios = createScenarioComparison(data,scenarioContext);
const presenting = ref(false);
watch([data,asOf,dataset,settings.dirty],() => { presenting.value = false }, { flush: 'sync' });
const validationIssues = computed(() => (error.value?.data as { validation?: { errors: DataIssue[] } } | undefined)?.validation?.errors ?? []);
async function selectFile(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (file) await upload.load(file);
  input.value = '';
}
function apply() { if (settings.apply()) stored.value = { ...settings.applied.value }; }
function reset() { settings.reset(); stored.value = { ...settings.applied.value }; }
const summary = computed(() => data.value ? proposalSummary(data.value) : null);
const unservedByReason = computed(() => {
  const counts = new Map<string, number>();
  for (const stop of data.value?.plan.unserved ?? []) counts.set(REASON_LABELS[stop.reason], (counts.get(REASON_LABELS[stop.reason]) ?? 0) + 1);
  return [...counts];
});
function exportSheet() { if (data.value) downloadCsv(proposalCsv(data.value), `route-proposal-${data.value.planDate}.csv`); }
function useAsPlan() {
  if (!data.value || dataset.value || settings.dirty.value) return;
  if (!plan.applyProposal(data.value)) return;
  view.value = 'manifest';
}
</script>
<template>
  <div class="page-body">
    <header class="section-title">
      <div>
        <p class="eyebrow">FORECAST & ROUTE PROPOSAL</p>
        <h1>Plan your next collection.</h1>
        <nav class="proposal-workflow" aria-label="Forecast and simulation sections"><a href="#proposal-setup"><span>1</span> Set your options</a><a href="#route-proposal"><span>2</span> Review routes</a><a href="#simulation"><span>3</span> Test a scenario</a></nav>
        <p v-if="ready && data">Uses collection records through {{ asOf }} only. Proposal for the next collection day: <strong>{{ data.planDate }}</strong>.</p>
        <p v-else>Uses collection records through {{ asOf }} only.</p>
      </div>
    </header>
    <section id="proposal-setup" class="proposal-setup" aria-label="Set your options">
      <UiCard class="proposal-dataset">
        <div class="proposal-dataset-current"><span class="eyebrow">DATA SOURCE</span><strong>{{ dataset ? dataset.name : 'Original collection records' }}</strong><span>History through {{ asOf }}</span></div>
        <details class="proposal-disclosure">
          <summary>Import a different CSV <span>Optional</span></summary>
          <div class="proposal-disclosure-content">
            <p>Use your own readings for routes, forecasts and simulation. The original inventory stays unchanged. Road routes require coordinates for each location; readings without coordinates can still be inspected and forecast.</p>
            <label>Readings CSV (up to 2 MB)<input type="file" accept=".csv,text/csv" :disabled="upload.reading.value" @change="selectFile" /></label>
            <p>Required columns: Location_id, material_type, date, fill_level_perc. Dates: YYYY-MM-DD. Materials: brown, green, white. Fill: integer 0–100 or overfull.</p>
          </div>
        </details>
        <UiButton v-if="dataset" label="Use original dataset" mode="outline" @click="upload.clear" />
        <p v-if="upload.error.value" role="alert">{{ upload.error.value }}</p>
        <div v-if="validationIssues.length" role="alert"><p>Upload rejected. No rows were silently removed. Correct the file and upload it again.</p><ul><li v-for="(issue, i) in validationIssues" :key="i">Row {{ issue.row_number }} · {{ issue.rule_id }}: {{ issue.message }}</li></ul></div>
      </UiCard>
      <ProposalSettingsForm :settings="settings.draft.value" :errors="settings.errors.value" :dirty="settings.dirty.value"
        @number="settings.setNumber" @flag="settings.setFlag" @apply="apply" @reset="reset" />
    </section>
    <div class="proposal-section-heading"><p class="eyebrow">2 · REVIEW ROUTES</p><h2>Your collection proposal</h2><p>Calculated with your applied options. Review the route before accepting it.</p></div>
    <UiInfoCard v-if="settings.dirty.value" headline="You have unapplied changes" color="warning" role="status"><p>Apply your options above to update these routes and enable simulation.</p></UiInfoCard>
    <WorkspaceState v-if="error" state="error" title="Proposal unavailable" :description="problem || 'Check the API connection, the selected date and the operating numbers.'" action="Retry" @action="refresh()" />
    <WorkspaceState v-else-if="status === 'pending'" state="loading" title="Forecasting fill levels and planning routes" description="Later observations are excluded from the forecast." />
    <template v-else-if="ready && data && summary">
      <WorkspaceState v-if="!data.bins.length" state="empty" title="No collections by this date" description="Choose a later planning date to get a proposal." />
      <template v-else>
        <div class="plan-metrics">
          <MetricCard label="TRUCKS NEEDED" :value="data.plan.totals.trucks" :caption="`${data.plan.totals.trips} loads · up to ${data.settings.maxVehicles} available`" />
          <MetricCard label="STOPS SERVED" :value="data.plan.totals.stops" :caption="`${summary.mandatoryStops - summary.unservedMandatory} urgent · ${summary.optionalStops - summary.unservedOptional} of ${summary.optionalStops} optional`" />
          <MetricCard label="CONTAINERS EMPTIED" :value="data.plan.totals.bins" :caption="`${summary.due} are due · the rest sit at sites a truck visits anyway`" />
          <MetricCard label="WORKING TIME" :value="formatHours(data.plan.totals.hours)" :caption="`All trucks together · about ${data.plan.totals.weightT.toFixed(1)} t of glass`" compact />
        </div>
        <UiInfoCard headline="Street routes · coordinated service sectors">
          <p>{{ data.plan.totals.distanceKm?.toFixed(1) ?? '—' }} km on car-accessible streets. Each truck serves a compact sector across its loads. Road distance is the routing objective; estimated driving times, collection service, unloading and the yard return must fit the shift.</p>
        </UiInfoCard>
        <UiInfoCard v-if="summary.unservedMandatory" headline="Some urgent stops do not fit" color="danger" role="alert">
          <p>{{ summary.unservedMandatory }} stops that must be emptied are not in the plan. Review the reasons below; adjust available trucks, shift length or the routing search budget before dispatch.</p>
        </UiInfoCard>
        <UiInfoCard v-if="!data.settings.brownCompartmentM3" headline="Glass compartment sizes are unknown"><p>This plan enforces total volume and payload only. Enter the actual brown, green and white capacities in Glass compartments above to check each colour separately.</p></UiInfoCard>
        <OperatingCosts :costs="data.costs" />
        <ScenarioComparison :proposal="data" :baseline="scenarios.baseline.value" :dirty="settings.dirty.value" @save="scenarios.save" @clear="scenarios.clear" />
        <UiButton label="Present this plan" mode="outline" :disabled="settings.dirty.value" @click="presenting = true" />
        <PlanPresentation v-if="presenting" :proposal="data" :baseline="scenarios.baseline.value" @close="presenting = false" @export="exportSheet" />
        <UiCard id="route-proposal" class="analytics-panel">
          <h2>Proposed routes for {{ data.planDate }}</h2>
          <p>A truck unloads when its next stop would exceed the load limit and then continues. Fill levels and weights are forecasts, not measurements.</p>
          <ProposalRouteMap :proposal="data" :locations="dataset ? [] : clusters" />
          <ProposalRoutesTable :proposal="data" />
          <ul v-if="unservedByReason.length" class="proposal-unserved">
            <li v-for="[reason, count] in unservedByReason" :key="reason">{{ count }} stops not served — {{ reason }}</li>
          </ul>
          <div class="proposal-actions">
            <UiButton label="Use as collection plan" :disabled="!data.plan.routes.length || !!dataset || settings.dirty.value" @click="useAsPlan" />
            <UiButton label="Download route sheet (CSV)" mode="outline" :disabled="!data.plan.routes.length" @click="exportSheet" />
          </div>
          <p v-if="dataset">Export uploaded-data routes here. The collection manifest uses the original inventory; switch back to the original dataset to accept a plan there.</p>
        </UiCard>
        <FillTimingTable :rows="data.fillTiming ?? []" />
        <ForecastAnalysis :as-of="asOf" :settings="stored" :settings-dirty="settings.dirty.value" :proposal="data" :dataset="dataset" />
        <div class="proposal-section-heading"><p class="eyebrow">SUPPORTING DETAILS</p><h2>Understand the forecast</h2><p>Inspect overflow risk, data quality and model assumptions.</p></div>
        <details class="proposal-disclosure proposal-support"><summary>Containers most likely to overflow</summary>
        <UiCard class="analytics-panel">
          <h2>Containers most likely to overflow</h2>
          <p>Overflow risk is the chance that a container is full by {{ data.windowEnd }}, the collection day after the plan date.</p>
          <ProposalRiskTable :proposal="data" />
        </UiCard>
        </details>
        <details v-if="data.dataset" class="proposal-disclosure proposal-support"><summary>Data quality & behavioral groups</summary><ProposalDataEvidence :evidence="data.dataset" /></details>
        <details class="proposal-disclosure proposal-support"><summary>How the forecast works & assumptions</summary>
        <UiCard class="analytics-panel proposal-model">
          <h2>How the forecast works</h2>
          <p>The seasonal cycle model learns from {{ data.model.cycles.toLocaleString('en-US') }} filling periods ({{ data.model.censoredCycles.toLocaleString('en-US') }} censored). Container rates borrow from glass-type averages, with month and school-vacation effects.</p>
          <p v-if="data.model.vacationMultiplier != null">Fitted school-vacation multiplier: {{ data.model.vacationMultiplier.toFixed(2) }}. This is a model association, not proof of causality.</p>
          <details v-if="data.model.seasonality?.length"><summary>Fitted monthly rate multipliers</summary><table><thead><tr><th>Month</th><th>Multiplier</th></tr></thead><tbody><tr v-for="row in data.model.seasonality" :key="row.month"><td>{{ row.month }}</td><td>{{ row.multiplier.toFixed(2) }}</td></tr></tbody></table></details>
          <dl>
            <template v-for="(rate, material) in data.model.materialRatePercentPerDay" :key="material">
              <dt><GlassFractionBadge :material="String(material)" /></dt><dd>typically {{ rate.toFixed(1) }} points of fill per day</dd>
            </template>
          </dl>
          <h3>Assumptions</h3>
          <ul><li v-for="text in data.assumptions" :key="text">{{ text }}</li></ul>
        </UiCard>
        </details>
      </template>
    </template>
  </div>
</template>
