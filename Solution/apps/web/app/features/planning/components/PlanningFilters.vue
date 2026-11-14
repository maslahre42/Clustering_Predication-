<script setup lang="ts">
const { search, material, minimumFill, sort, resetFilters } = usePlanningFilters();
const fractions = [{ value: '', label: 'All glass' }, { value: 'brown', label: 'Brown' }, { value: 'green', label: 'Green' }, { value: 'white', label: 'White' }];
</script>
<template>
  <div class="planning-filters">
    <div class="fraction-filter">
      <span class="field-caption">GLASS FRACTION</span>
      <UiSegmentedControl v-model="material" :options="fractions" name="glass-fraction" density="compact" />
    </div>
    <div class="threshold-filter">
      <UiSlider v-model="minimumFill" :min="0" :max="100" :step="5" :label="`Recorded fill ≥ ${minimumFill}%`" density="compact" />
    </div>
    <UiSelect v-model="sort" :allow-empty="false" label="Sort locations" list-label="Location sort order" :options="[{ value: 'recent', label: 'Latest collection' }, { value: 'fill', label: 'Highest recorded fill' }]" density="compact" />
    <div class="search-filter">
      <UiInput v-model="search" label="Find a location" type="search" placeholder="Search location UUID…" density="compact" />
    </div>
    <UiButton label="Reset filters" mode="plain" @click="resetFilters" />
  </div>
</template>
