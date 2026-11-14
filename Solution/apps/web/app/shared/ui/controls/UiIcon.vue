<script setup lang="ts">
// Icons are trusted, static SVG strings from shared/ui/icons.ts, never user content.
defineProps<{
  icon: string;
}>();
</script>
<template>
  <span class="ui-icon" aria-hidden="true" v-html="icon" />
</template>
