<script setup lang="ts">
import { workspaceIcons } from '~/shared/ui/icons';
const { asOf, bounds, applyPlanningDate, dateRangeRequest } = usePlanningDate();
const { error: rangeError, status: rangeStatus } = dateRangeRequest;
</script>
<template>
  <header class="workspace-header">
    <div>
      <strong>Garbage Collector</strong>
    </div>
    <div class="header-date">
      <div class="planning-date-control">
        <CollectionDatePicker :model-value="asOf" label="Planning date" hide-label :min="bounds?.firstDate" :max="bounds?.maxPlanningDate" :disabled="!bounds || !!rangeError" required confirm @apply="applyPlanningDate" />
        <small v-if="rangeError" role="alert">Unable to load available dates.</small>
        <small v-else-if="rangeStatus === 'pending'">Loading available dates…</small>
        <small v-else-if="!bounds">No recorded dates available.</small>
      </div>
    </div>
    <UiTag class="workspace-lock" label="Locked" :icon="workspaceIcons.lock" :title="`Historical cutoff locked to ${asOf}. Later records excluded.`" color="neutral" />
  </header>
</template>
