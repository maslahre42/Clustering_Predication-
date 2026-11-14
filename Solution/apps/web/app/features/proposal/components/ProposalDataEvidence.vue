<script setup lang="ts">
import type { DatasetEvidence } from '~/shared/api/contracts/comparison';
defineProps<{ evidence: DatasetEvidence }>();
const label = (value: string) => value.replaceAll('_', ' ');
</script>
<template>
  <UiCard class="analytics-panel">
    <h2>Data quality & behavioral groups</h2>
    <p>Kaise’s validation and interpretability safeguards · {{ evidence.rows }} observations · {{ evidence.bins }} containers · {{ evidence.dateMin || '—' }}–{{ evidence.dateMax || '—' }}.</p>
    <p>{{ evidence.unknown }} unknown readings · {{ evidence.overfull }} overfull observations · {{ evidence.warnings.length }} validation warnings. Unknown and overfull retain separate meanings.</p>
    <p>Grouping: <strong>{{ evidence.grouping.method === 'kmeans' ? 'Interpretable clusters' : 'Descriptive pressure tiers' }}</strong>. {{ evidence.grouping.eligible }} eligible containers; {{ evidence.grouping.insufficient }} with insufficient history.</p>
    <p>{{ evidence.grouping.note }}</p>
    <table><thead><tr><th>Group</th><th>Containers</th><th>Mean observed fill (group median)</th><th>Cycle rate (group median)</th></tr></thead><tbody>
      <tr v-for="profile in evidence.grouping.profiles" :key="profile.label"><td>{{ label(profile.label) }}</td><td>{{ profile.n_series }}</td><td>{{ profile.feature_medians.mean_fill_pct?.toFixed(1) ?? '—' }}%</td><td>{{ profile.feature_medians.median_rate_pct_per_day?.toFixed(2) ?? '—' }} pp/day</td></tr>
    </tbody></table>
    <details><summary>Grouping checks and container assignments</summary>
      <p v-if="!Object.keys(evidence.grouping.gate).length">Not enough eligible or distinct histories to test meaningful clusters; pressure tiers are used.</p>
      <ul><li v-for="(passed, name) in evidence.grouping.gate" :key="name">{{ label(name) }}: {{ passed ? 'passed' : 'failed — tiers used' }}</li></ul>
      <div class="table-scroll"><table><thead><tr><th>Location</th><th>Material</th><th>Group</th></tr></thead><tbody><tr v-for="row in evidence.grouping.labels" :key="`${row.locationId}:${row.material}`"><td>{{ row.locationId }}</td><td>{{ row.material }}</td><td>{{ label(row.group) }}</td></tr></tbody></table></div>
    </details>
    <details v-if="evidence.warnings.length"><summary>Validation warnings</summary><ul><li v-for="(issue, i) in evidence.warnings" :key="i">Row {{ issue.row_number }} · {{ issue.rule_id }}: {{ issue.message }}</li></ul></details>
    <p class="data-note">Snapshot {{ evidence.fingerprint.slice(0, 12) }} · {{ evidence.source }}. Original observations remain unchanged.</p>
  </UiCard>
</template>
