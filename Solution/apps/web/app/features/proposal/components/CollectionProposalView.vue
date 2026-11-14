<script setup lang="ts">
import type { ProposalSettings } from '~/shared/api/contracts/proposal';
import { downloadCsv } from '~/shared/browser/download';
import { useCollectionProposal } from '../composables/useCollectionProposal';
import { REASON_LABELS, formatHours, proposalCsv, proposalSummary, servedBinKeys, servedOrder } from '../domain/proposal';
import { DEFAULT_PROPOSAL_SETTINGS } from '../domain/settings';
import { createProposalSettings } from '../state/createProposalSettings';

const { asOf } = useWorkspaceData();
const { view } = useWorkspaceNavigation();
const plan = useCollectionPlan();
// Applied settings survive switching between workspace modules.
const stored = useState<ProposalSettings>('proposal-settings', () => ({ ...DEFAULT_PROPOSAL_SETTINGS }));
const settings = createProposalSettings(stored.value);
const { data, error, status, refresh, ready, problem } = useCollectionProposal(asOf, stored);

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
  if (!data.value) return;
  plan.applyProposal(servedBinKeys(data.value), servedOrder(data.value));
  view.value = 'manifest';
}
</script>
<template>
  <div class="page-body">
    <header class="section-title">
      <div>
        <p class="eyebrow">FORECAST & ROUTE PROPOSAL</p>
        <h1>What to empty next, and with how many trucks.</h1>
        <p v-if="ready && data">Uses collection records through {{ asOf }} only. Proposal for the next collection day: <strong>{{ data.planDate }}</strong>.</p>
        <p v-else>Uses collection records through {{ asOf }} only.</p>
      </div>
    </header>
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
        <UiInfoCard v-if="summary.unservedMandatory" headline="Some urgent stops do not fit" color="danger" role="alert">
          <p>{{ summary.unservedMandatory }} stops that must be emptied are not in the plan. Add trucks or lengthen the shift below.</p>
        </UiInfoCard>
        <UiCard class="analytics-panel">
          <h2>Proposed routes for {{ data.planDate }}</h2>
          <p>A truck unloads when its next stop would exceed the load limit and then continues. Fill levels and weights are forecasts, not measurements.</p>
          <ProposalRoutesTable :proposal="data" />
          <ul v-if="unservedByReason.length" class="proposal-unserved">
            <li v-for="[reason, count] in unservedByReason" :key="reason">{{ count }} stops not served — {{ reason }}</li>
          </ul>
          <div class="proposal-actions">
            <UiButton label="Use as collection plan" :disabled="!data.plan.routes.length" @click="useAsPlan" />
            <UiButton label="Download route sheet (CSV)" mode="outline" :disabled="!data.plan.routes.length" @click="exportSheet" />
          </div>
        </UiCard>
        <ProposalSettingsForm :settings="settings.draft.value" :errors="settings.errors.value" :dirty="settings.dirty.value"
          @number="settings.setNumber" @flag="settings.setFlag" @apply="apply" @reset="reset" />
        <UiCard class="analytics-panel">
          <h2>Containers most likely to overflow</h2>
          <p>Overflow risk is the chance that a container is full by {{ data.windowEnd }}, the collection day after the plan date.</p>
          <ProposalRiskTable :proposal="data" />
        </UiCard>
        <UiCard class="analytics-panel proposal-model">
          <h2>How the forecast works</h2>
          <p>Each visit empties the container, so the fill recorded at a visit is what accumulated since the previous one. From {{ data.model.cycles.toLocaleString('en-US') }} such filling periods ({{ data.model.censoredCycles.toLocaleString('en-US') }} ended full and count as “at least this fast”) the model learns a fill rate per container, pulled towards the average of its glass type when a container has few visits.</p>
          <dl>
            <template v-for="(rate, material) in data.model.materialRatePercentPerDay" :key="material">
              <dt><GlassFractionBadge :material="String(material)" /></dt><dd>typically {{ rate.toFixed(1) }} points of fill per day</dd>
            </template>
          </dl>
          <h3>Assumptions</h3>
          <ul><li v-for="text in data.assumptions" :key="text">{{ text }}</li></ul>
        </UiCard>
      </template>
    </template>
  </div>
</template>
