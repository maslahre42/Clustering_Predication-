<script setup lang="ts">
import { Comment, Fragment, Text, type VNode } from 'vue';
defineProps<{
  tableAttrs?: Record<string, unknown>;
  density?: string;
}>();
function hasRows(nodes: VNode[]): boolean {
  return nodes.some(node => node.type === Fragment ? hasRows(node.children as VNode[]) : node.type !== Comment && node.type !== Text);
}
</script>
<template>
  <div class="ui-table">
    <div class="ui-table-scroll">
      <table v-bind="tableAttrs">
        <thead><slot name="head" /></thead>
        <tbody><slot /></tbody>
      </table>
    </div>
    <p v-if="!hasRows($slots.default?.() ?? [])" class="ui-table-empty">
      <slot name="empty">No records available.</slot>
    </p>
    <footer v-if="$slots.pagination || $slots.bottomLeft" class="ui-table-footer">
      <span><slot name="bottomLeft" /></span>
      <slot name="pagination" />
    </footer>
  </div>
</template>
