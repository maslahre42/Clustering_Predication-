<script setup lang="ts">
import { workspaceIcons } from '~/shared/ui/icons';
import type { WorkspaceView } from '~/features/workspace/model';
const { view } = useWorkspaceNavigation();
const sections: { id: Exclude<WorkspaceView, 'details'>; label: string }[] = [
  { id: 'planning', label: 'Route planner & map' }, { id: 'history', label: 'Bin inventory & history' },
  { id: 'analytics', label: 'Historical analytics' }, { id: 'forecasts', label: 'Forecast & route proposal' },
  { id: 'manifest', label: 'Collection plan' }, { id: 'status', label: 'System status' },
];
</script>
<template>
  <aside class="workspace-sidebar">
    <div class="rail-brand" aria-label="Garbage Collector"><UiIcon :icon="workspaceIcons.recycling" /></div>
    <nav class="module-nav" aria-label="Workspace modules">
      <button v-for="section in sections" :key="section.id" type="button" :aria-label="section.label" :title="section.label" :aria-current="view === section.id || (section.id === 'history' && view === 'details') ? 'page' : undefined" @click="view = section.id">
        <UiIcon :icon="workspaceIcons[section.id]" /><span class="rail-tooltip">{{ section.label }}</span>
      </button>
    </nav>
  </aside>
</template>
