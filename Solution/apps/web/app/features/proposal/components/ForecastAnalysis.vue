<script setup lang="ts">
import { computed, onScopeDispose, toRef } from 'vue';
import type { CollectionProposal, ProposalSettings } from '~/shared/api/contracts/proposal';
import type { ForecastCurve, SimulationResult } from '~/shared/api/contracts/simulation';
import type { ProposalDataset } from '~/shared/api/contracts/comparison';
import { API_ROUTES } from '~/shared/api/routes';
import { createAnalysisState } from '../state/createAnalysisState';
const props = defineProps<{ asOf: string; settings: ProposalSettings; proposal: CollectionProposal; dataset: ProposalDataset | null; settingsDirty?: boolean }>();
const analysis = createAnalysisState(toRef(props, 'asOf'), toRef(props, 'settings'), {
  forecast: (query, signal) => $fetch<ForecastCurve>(API_ROUTES.forecast, { query, signal, timeout: 240000, ...(props.dataset ? { method: 'POST', body: { csv: props.dataset.csv } } : {}) }),
  simulation: (query, signal) => $fetch<SimulationResult>(API_ROUTES.simulation, { query, signal, timeout: 240000, ...(props.dataset ? { method: 'POST', body: { csv: props.dataset.csv } } : {}) }),
}, toRef(props, 'dataset'));
onScopeDispose(analysis.dispose);
const bins = computed(() => props.proposal.bins.filter(b => b.expectedFillPercent != null));
const { forecastInput, simulationInput, forecast, simulation, forecasting, simulating, forecastError, simulationError } = analysis;
function choose(value: string) {
  const bin = bins.value.find(b => `${b.locationId}:${b.material}` === value);
  if (bin) forecastInput.value = { ...forecastInput.value, locationId: bin.locationId, material: bin.material };
}
</script>
<template>
  <UiCard id="simulation" class="analytics-panel">
    <p class="eyebrow">3 · TEST A SCENARIO</p>
    <h2>Simulation & backtest</h2>
    <p>Compare collection policies over a past period using your applied settings. Choose up to 31 days ending on or before {{ asOf }}.</p>
    <details class="proposal-disclosure"><summary>What does the simulation compare?</summary><p>Replay the recorded collection calendar and compare it with Omar’s dynamic policy and Zakaria’s corrected median policy. Kaise’s persistence is evaluated separately against real readings. Training ends before the simulation starts.</p></details>
    <p v-if="settingsDirty" class="proposal-settings-notice" role="status">Apply your collection settings above before running a simulation.</p>
    <div class="proposal-analysis-controls">
      <label>Start<input v-model="simulationInput.start" type="date" :max="asOf" /></label>
      <label>End<input v-model="simulationInput.end" type="date" :max="asOf" /></label>
      <label>Random seed<input v-model.number="simulationInput.seed" type="number" min="0" max="1000000" /></label>
      <UiButton :label="simulating ? 'Running daily routes…' : 'Run simulation'" :disabled="simulating || settingsDirty" @click="!settingsDirty && analysis.runSimulation()" />
    </div>
    <p v-if="simulating" role="status">Fitting the pre-period model and routing both policies day by day. This can take a few minutes; shorter windows run faster.</p>
    <p v-if="simulationError" role="alert">{{ simulationError }}</p>
    <SimulationResults v-if="simulation && !settingsDirty" :result="simulation" />
  </UiCard>
  <details class="proposal-disclosure proposal-support">
    <summary>Explore individual forecast curves</summary>
  <UiCard id="forecast-explorer" class="analytics-panel">
    <h2>Explore a container’s forecast</h2>
    <p>See how one container may fill over time. The model uses collection history through {{ asOf }} only.</p>
    <div class="proposal-analysis-controls">
      <label>Container<select :value="`${forecastInput.locationId}:${forecastInput.material}`" @change="choose(($event.target as HTMLSelectElement).value)">
        <option value=":white">Choose a container</option><option v-for="bin in bins" :key="`${bin.locationId}:${bin.material}`" :value="`${bin.locationId}:${bin.material}`">{{ bin.locationId.slice(0, 8) }} · {{ bin.material }}</option>
      </select></label>
      <label>Forecast horizon (days)<input v-model.number="forecastInput.horizonDays" type="number" min="1" max="150" /></label>
      <UiButton :label="forecasting ? 'Calculating forecast…' : 'Show forecast'" :disabled="forecasting || settingsDirty" @click="!settingsDirty && analysis.runForecast()" />
    </div>
    <p v-if="forecastError" role="alert">{{ forecastError }}</p>
    <ForecastExplorer v-if="forecast && !settingsDirty" :forecast="forecast" />
  </UiCard>
  </details>
</template>
