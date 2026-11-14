<script setup lang="ts">
defineProps<{
  headline: string;
  color?: string;
}>();
</script>
<template>
  <section :class="['ui-info-card', { 'ui-info-card--danger': color === 'danger' }]">
    <h3>{{ headline }}</h3>
    <slot />
  </section>
</template>
