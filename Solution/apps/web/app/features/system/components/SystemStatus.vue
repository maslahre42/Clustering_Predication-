<script setup lang="ts">
import { computed, onScopeDispose, ref } from 'vue';
import type { ProposalDataset } from '~/shared/api/contracts/comparison';
import type { DatasetValidation } from '~/shared/api/contracts/dataset';
import { API_ROUTES } from '~/shared/api/routes';
import { workspaceIcons } from '~/shared/ui/icons';
import { createProposalDataset } from '~/features/proposal/state/createProposalDataset';
const { healthRequest, snapshotRequest, ready, asOf, bins, clusters, retry, loading } = useWorkspaceData();
const { view } = useWorkspaceNavigation();
const dataset = useState<ProposalDataset | null>('proposal-dataset', () => null);
const metadata = useState<DatasetValidation | null>('proposal-dataset-metadata', () => null);
const upload = createProposalDataset(dataset, {
  metadata,
  validate: (csv, signal) => $fetch<DatasetValidation>(API_ROUTES['dataset-validation'], { method: 'POST', query: { asOf: asOf.value }, body: { csv }, signal, timeout: 240000 }),
});
onScopeDispose(upload.dispose);
const { error, reading, phase, dragging, issues } = upload;
const picker = ref<HTMLInputElement>();
const healthy = computed(() => healthRequest.data.value?.status === 'healthy' && !healthRequest.error.value);
const fileInfo = computed(() => dataset.value ? metadata.value : null);
const recordCount = computed(() => dataset.value ? fileInfo.value?.rows : ready.value ? snapshotRequest.data.value?.observationCount : null);
const locationCount = computed(() => dataset.value ? fileInfo.value?.locations : ready.value ? clusters.value.length : null);
const binCount = computed(() => dataset.value ? fileInfo.value?.bins : ready.value ? bins.value.length : null);
const firstDate = computed(() => dataset.value ? fileInfo.value?.firstDate : snapshotRequest.data.value?.firstDate);
const lastDate = computed(() => dataset.value ? fileInfo.value?.lastDate : snapshotRequest.data.value?.lastDate);
const futureOnly = computed(() => !!dataset.value && !!fileInfo.value?.firstDate && fileInfo.value.firstDate > asOf.value);
async function choose(event: Event) {
  const input = event.target as HTMLInputElement;
  await upload.receiveFiles(input.files);
  input.value = '';
}
</script>
<template>
  <div class="page-body data-page">
    <header class="section-title">
      <div><p class="eyebrow">DATA & IMPORTS</p><h1>Your data, ready to plan.</h1><p>Bring your collection records into the workspace. Check the file here, then explore forecasts, collection schedules and costs.</p></div>
      <UiTag :label="healthy ? 'Database connected' : healthRequest.status.value === 'pending' ? 'Checking connection' : 'Check connection'" :color="healthy ? 'success' : 'neutral'" />
    </header>
    <div class="data-workspace-grid">
      <UiCard class="data-import-panel">
        <div class="data-panel-heading"><span class="data-step">01</span><div><p class="eyebrow">COLLECTION RECORDS</p><h2>Import your CSV</h2></div><span class="data-format-badge">CSV · up to 2 MB</span></div>
        <section class="data-dropzone" :class="{ 'is-dragging': dragging, 'is-checking': reading }" aria-label="CSV upload drop zone" :aria-busy="reading"
          @dragenter.prevent="upload.dragEnter($event.dataTransfer?.types ?? [])" @dragover.prevent @dragleave.prevent="upload.dragLeave" @drop.stop.prevent="upload.drop($event.dataTransfer?.files)">
          <div class="data-upload-icon"><UiIcon :icon="workspaceIcons.upload" /></div>
          <h3>{{ dragging ? 'Drop to check your file' : reading ? 'Getting your data ready' : 'Drop your CSV here' }}</h3>
          <p>{{ reading ? phase : 'Drag a file into this box, or choose one from your device.' }}</p>
          <input ref="picker" type="file" accept=".csv,text/csv" hidden aria-label="Choose collection CSV" @change="choose" />
          <UiButton :label="reading ? 'Checking your CSV…' : dataset ? 'Choose another CSV' : 'Choose CSV file'" :loading="reading" @click="picker?.click()" />
          <span class="data-dropzone-note">One CSV file · checked before it becomes active</span>
        </section>
        <div v-if="error" class="data-import-feedback data-import-feedback--error" role="alert"><strong>We couldn’t use this file</strong><p>{{ error }}</p><p>The active dataset is unchanged. Row numbers include the header.</p><ul v-if="issues.length"><li v-for="(issue,i) in issues.slice(0,8)" :key="i">{{ issue.row_number ? `Row ${issue.row_number + 1}` : 'File' }}: {{ issue.message }}</li></ul><details v-if="issues.length>8"><summary>Show {{ issues.length-8 }} more issues</summary><ul><li v-for="(issue,i) in issues.slice(8)" :key="i">{{ issue.row_number ? `Row ${issue.row_number + 1}` : 'File' }}: {{ issue.message }}</li></ul></details></div>
        <div v-else-if="dataset && fileInfo && !reading" class="data-import-feedback data-import-feedback--success" role="status"><UiIcon :icon="workspaceIcons.check" /><div><strong>{{ dataset.name }} is ready</strong><p>Columns and collection records checked. Your file is now selected for analysis.</p></div></div>
        <details class="data-format-help"><summary>What should my CSV contain?</summary><p>Use these four columns, with one collection record per row.</p><div class="data-schema-scroll"><code>Location_id,material_type,date,fill_level_perc<br>site-001,white,2026-09-01,80</code></div><div class="data-format-rules"><span><strong>Date</strong> YYYY-MM-DD</span><span><strong>Glass type</strong> brown, green or white</span><span><strong>Fill</strong> integer 0–100, or overfull</span></div><p>Readings describe fill before emptying. Uploaded readings do not include location coordinates; street routes require a matching coordinate source.</p></details>
      </UiCard>
      <UiCard class="data-active-panel">
        <div class="data-panel-heading"><span class="data-step">02</span><div><p class="eyebrow">SELECTED FOR ANALYSIS</p><h2>Your working dataset</h2></div></div>
        <div class="data-active-file"><div class="data-file-symbol"><UiIcon :icon="dataset ? workspaceIcons.file : workspaceIcons.status" /></div><div><strong>{{ dataset?.name ?? 'Collection database' }}</strong><span>{{ dataset ? fileInfo ? 'CSV checked and ready' : 'CSV selected' : 'Connected collection history' }}</span></div><span class="data-active-indicator">Active</span></div>
        <div class="data-summary-grid"><div><span>Records</span><strong>{{ recordCount?.toLocaleString() ?? '—' }}</strong></div><div><span>Locations</span><strong>{{ locationCount?.toLocaleString() ?? '—' }}</strong></div><div><span>Site / glass types</span><strong>{{ binCount?.toLocaleString() ?? '—' }}</strong></div><div><span>History cutoff</span><strong class="data-date-value">{{ asOf }}</strong></div></div>
        <div class="data-history-range"><span>Records available</span><strong>{{ firstDate ?? 'No records' }} <span aria-hidden="true">→</span> {{ lastDate ?? 'No records' }}</strong></div>
        <p v-if="futureOnly" class="data-import-feedback data-import-feedback--notice" role="status">This file starts after the selected planning date. Select a date with available records before calculating forecasts.</p>
        <p class="data-source-note">{{ dataset ? 'This CSV is used in Forecast, routes & simulation. Inventory and historical analytics continue to use the collection database.' : 'Forecasts, scenarios and history currently use the connected collection database.' }} Analysis uses records on or before {{ asOf }}.</p>
        <UiButton label="Open forecasts & optimization" :disabled="reading || futureOnly" @click="view = 'forecasts'" />
        <UiButton v-if="dataset" label="Use collection database" mode="outline" @click="upload.clear" />
        <p class="data-session-note">CSV selection stays in this workspace session. Importing does not overwrite the collection database.</p>
        <details v-if="fileInfo?.warnings.length" class="data-format-help"><summary>{{ fileInfo.warnings.length }} data notes</summary><ul><li v-for="(warning,i) in fileInfo.warnings" :key="i">{{ warning.row_number ? `Row ${warning.row_number + 1}: ` : '' }}{{ warning.message }}</li></ul></details>
      </UiCard>
    </div>
    <section class="data-connections" aria-label="Data connections">
      <div><h2>Workspace connections</h2><p>Keep the source visible and your next calculation in context.</p></div><UiButton label="Refresh connection" mode="outline" :loading="loading" @click="retry" />
      <div class="data-connection-card"><span class="connection-dot" :class="{ connected: healthy }" /><div><strong>Collection database</strong><p>{{ healthy ? 'Available · original collection records' : 'Connection needs checking' }}</p></div><span class="data-connection-detail">Read-only source</span></div>
      <div class="data-connection-card"><UiIcon :icon="workspaceIcons.planning" /><div><strong>Street routing & maps</strong><p>OSRM / OpenStreetMap · car-street routes</p></div><span class="data-connection-detail">Checked when routes are calculated</span></div>
      <details class="data-connection-diagnostics"><summary>Connection & workspace details</summary><dl><dt>Planning history</dt><dd>{{ ready ? 'Loaded for the selected date' : 'Waiting for the collection database' }}</dd><dt>Forecasting</dt><dd>Seasonal filling model and container/schedule optimization</dd><dt>Saved plans</dt><dd>Workspace drafts and completed analysis; export a CSV to keep a copy</dd><dt>Recorded emptyings</dt><dd>Only collection records reset modelled fill; generating a route does not record an emptying</dd></dl></details>
    </section>
  </div>
</template>
