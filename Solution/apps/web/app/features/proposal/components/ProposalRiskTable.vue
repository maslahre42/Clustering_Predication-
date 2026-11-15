<script setup lang="ts">
import { computed } from 'vue';
import type { CollectionProposal } from '~/shared/api/contracts/proposal';
import { DECISION_HELP, DECISION_LABELS, formatPercent, formatRisk, topRisks } from '~/features/proposal/domain/proposal';

const props = withDefaults(defineProps<{ proposal: CollectionProposal; limit?: number }>(), { limit: 25 });
const rows = computed(() => topRisks(props.proposal, props.limit));
</script>
<template>
  <UiTable :table-attrs="{ 'aria-label': 'Containers with the highest overflow risk' }" density="compact">
    <template #head>
      <tr>
        <th scope="col">Location</th><th scope="col">Glass</th><th scope="col">Last emptied</th><th scope="col">Days since</th>
        <th scope="col">Expected fill on {{ proposal.planDate }}</th><th scope="col">Overflow risk by {{ proposal.windowEnd }}</th><th scope="col">Decision</th>
      </tr>
    </template>
    <tr v-for="bin in rows" :key="`${bin.locationId}:${bin.material}`">
      <td :title="bin.locationId">Location {{ bin.locationId.slice(0, 8) }}</td>
      <td><GlassFractionBadge :material="bin.material" /></td>
      <td>{{ bin.lastEmptied }}</td>
      <td>{{ bin.daysSinceEmptied }}</td>
      <td>{{ formatPercent(bin.expectedFillPercent) }}</td>
      <td>{{ formatRisk(bin.overflowProbability) }}</td>
      <td :title="DECISION_HELP[bin.decision]">{{ DECISION_LABELS[bin.decision] }}</td>
    </tr>
  </UiTable>
</template>
