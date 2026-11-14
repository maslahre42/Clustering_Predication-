<script setup lang="ts">
import type { CollectionAnalytics } from '~/shared/api/contracts/analytics';
defineProps<{
    data: CollectionAnalytics;
}>();
</script>
<template>
  <div class="plan-metrics">
    <MetricCard label="RECORDED COLLECTIONS" :value="data.totalCollections.toLocaleString()" caption="Every eligible reading counts" />
    <MetricCard label="OVERFULL AT COLLECTION" :value="data.overfullCount.toLocaleString()" caption="Explicit categories, not invented 110% values" />
    <MetricCard label="KNOWN BINS" :value="data.knownBins" caption="Location UUID + glass fraction" />
    <MetricCard label="SPARSE BIN HISTORY" :value="data.binsWithFewerThan3Readings" caption="Fewer than 3 observations by this cutoff" />
  </div>
</template>
