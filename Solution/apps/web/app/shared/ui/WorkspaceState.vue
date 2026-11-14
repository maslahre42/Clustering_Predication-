<script setup lang="ts">
defineProps<{
    state: 'loading' | 'empty' | 'error' | 'unavailable';
    title: string;
    description: string;
    action?: string;
}>();
defineEmits<{
    action: [
    ];
}>();
</script>
<template>
  <div v-if="state === 'loading'" class="workspace-state" role="status">
    <UiLoadingIndicator />
    <h3>{{ title }}</h3>
    <p>{{ description }}</p>
  </div>
  <UiInfoCard v-else :headline="title" :color="state === 'error' ? 'danger' : 'neutral'" :class="['workspace-state', `state-${state}`]" :role="state === 'error' ? 'alert' : undefined">
    <p>{{ description }}</p>
    <UiButton v-if="action" :label="action" mode="outline" @click="$emit('action')" />
  </UiInfoCard>
</template>
