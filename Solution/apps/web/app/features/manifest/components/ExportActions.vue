<script setup lang="ts">
import { coordinateSourceLabel } from '~/shared/domain/coordinates';
import { printDatedDocument } from '~/shared/browser/print';
const { stops, exportCsv, routeOrder } = useCollectionPlan();
const printedAt = useState<string | null>('manifest-print-timestamp', () => null);
function printManifest() {
  return printDatedDocument({
    setTimestamp: value => { printedAt.value = value; },
    afterRender: nextTick,
    print: () => window.print(),
  });
}
</script>
<template>
  <UiCard class="export-actions">
    <h2>Export & hand-off</h2>
    <p>Download the dated plan or print a collector sheet. {{ coordinateSourceLabel(stops) }}; percentages are historical.</p>
    <UiButton label="Download CSV" :disabled="!stops.length" @click="exportCsv" />
    <UiButton label="Print / save as PDF" mode="outline" :disabled="!stops.length" @click="printManifest" />
    <UiButton label="Reorder by nearest neighbor" mode="plain" :disabled="!stops.length" @click="routeOrder = []" />
    <small>Driver dispatch and database synchronization are not connected.</small>
  </UiCard>
</template>
