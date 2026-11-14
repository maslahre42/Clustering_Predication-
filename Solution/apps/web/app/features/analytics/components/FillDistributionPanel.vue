<script setup lang="ts">
import type { MaterialAnalytics } from '~/shared/api/contracts/analytics';
defineProps<{
    materials: MaterialAnalytics[];
}>();
</script>
<template>
  <UiCard class="analytics-panel">
    <h2>Fill distribution at collection</h2>
    <p>Descriptive bands, not claims about whether a collection was necessary. Sparse histories and scheduling effects limit comparisons.</p>
    <div class="analytics-distributions">
      <article v-for="row in materials" :key="row.material">
        <GlassFractionBadge :material="row.material" />
        <dl>
          <dt>0–30%</dt>
          <dd>{{ row.distribution.low0To30 }}</dd>
          <dt>Above 30%, below 70%</dt>
          <dd>{{ row.distribution.midAbove30Below70 }}</dd>
          <dt>70%, below 100%</dt>
          <dd>{{ row.distribution.high70Below100 }}</dd>
          <dt>Exactly 100%</dt>
          <dd>{{ row.distribution.full100 }}</dd>
          <dt>Overfull</dt>
          <dd>{{ row.distribution.overfull }}</dd>
          <dt>Unknown</dt>
          <dd>{{ row.distribution.unknown }}</dd>
        </dl>
      </article>
    </div>
  </UiCard>
</template>
