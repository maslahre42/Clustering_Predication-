<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue';
import { calendarCells, calendarInitialDate, isCalendarDateAllowed, shiftCalendarDate, shiftCalendarMonth } from '../domain/calendar';
import { isIsoDate } from '../domain/dates';
import { workspaceIcons } from './icons';
const props = defineProps<{ modelValue?: string | null; label: string; hideLabel?: boolean; min?: string; max?: string; disabled?: boolean; required?: boolean; confirm?: boolean }>();
const emit = defineEmits<{ 'update:modelValue': [value: string | undefined]; apply: [value: string] }>();
const pending = ref(props.modelValue);
watch(() => props.modelValue, value => { pending.value = value; });
const selected = computed(() => props.confirm ? pending.value : props.modelValue);
const canApply = computed(() => !props.disabled && !!pending.value && pending.value !== props.modelValue && isCalendarDateAllowed(pending.value, props.min, props.max));
const id = useId();
const root = ref<HTMLDetailsElement>();
const today = ref('');
const month = ref(props.modelValue?.slice(0, 7) || props.min?.slice(0, 7) || new Date().toISOString().slice(0, 7));
const cells = computed(() => calendarCells(month.value, props.min, props.max, today.value));
const heading = computed(() => new Date(`${month.value}-01T12:00:00Z`).toLocaleDateString('en-GB', { month: 'long', year: 'numeric', timeZone: 'UTC' }));
const previousAllowed = computed(() => !props.min || shiftCalendarMonth(month.value, -1) >= props.min.slice(0, 7));
const nextAllowed = computed(() => !props.max || shiftCalendarMonth(month.value, 1) <= props.max.slice(0, 7));
function close(restoreFocus = false) {
  if (root.value) root.value.open = false;
  if (restoreFocus) root.value?.querySelector('summary')?.focus();
}
function choose(date: string) {
  if (props.disabled || !isCalendarDateAllowed(date, props.min, props.max)) return;
  if (props.confirm) { pending.value = date; return; }
  emit('update:modelValue', date);
  close();
  root.value?.querySelector('summary')?.focus();
}
function applySelection() {
  if (!canApply.value || !pending.value) return;
  emit('update:modelValue', pending.value);
  emit('apply', pending.value);
  close(true);
}
function clearSelection() {
  if (props.disabled || props.required) return;
  if (props.confirm) pending.value = undefined;
  else { emit('update:modelValue', undefined); close(true); }
}
function opened() {
  if (!root.value?.open) return;
  pending.value = props.modelValue;
  const initial = calendarInitialDate(props.modelValue, props.min, props.max, today.value);
  if (initial && isIsoDate(initial)) month.value = initial.slice(0, 7);
}
function outside(event: PointerEvent) { if (!root.value?.contains(event.target as Node)) close(); }
async function moveFocus(event: KeyboardEvent, date: string) {
  if (event.key === 'Escape') { close(true); return; }
  const offsets: Record<string, number> = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 };
  const offset = offsets[event.key];
  if (offset === undefined) return;
  event.preventDefault();
  const target = shiftCalendarDate(date, offset);
  if (!isCalendarDateAllowed(target, props.min, props.max)) return;
  month.value = target.slice(0, 7);
  await nextTick();
  root.value?.querySelector<HTMLButtonElement>(`[data-date="${target}"]`)?.focus();
}
onMounted(() => {
  const now = new Date();
  today.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  document.addEventListener('pointerdown', outside);
});
onBeforeUnmount(() => document.removeEventListener('pointerdown', outside));
</script>
<template>
  <div class="ui-field collection-date-picker">
    <label :id="`${id}-label`" :class="{ 'sr-only': hideLabel }">{{ label }}</label>
    <details ref="root" :class="{ 'is-disabled': disabled }" @toggle="opened" @keydown.esc.stop.prevent="close(true)">
      <summary :aria-labelledby="`${id}-label ${id}-value`" aria-haspopup="dialog" :aria-controls="`${id}-calendar`" :aria-disabled="disabled || undefined" :tabindex="disabled ? -1 : 0" @click="disabled && $event.preventDefault()">
        <UiIcon :icon="workspaceIcons.calendar" /><span :id="`${id}-value`">{{ modelValue || 'Select date' }}</span><UiIcon :icon="workspaceIcons.chevronDown" />
      </summary>
      <div :id="`${id}-calendar`" class="calendar-popover" role="dialog" :aria-label="label">
        <header><UiIconButton label="Previous month" :icon="workspaceIcons.chevronLeft" :disabled="!previousAllowed" @click="month = shiftCalendarMonth(month, -1)" /><strong aria-live="polite">{{ heading }}</strong><UiIconButton label="Next month" :icon="workspaceIcons.chevronRight" :disabled="!nextAllowed" @click="month = shiftCalendarMonth(month, 1)" /></header>
        <div class="calendar-weekdays" aria-hidden="true"><span v-for="day in ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']" :key="day">{{ day }}</span></div>
        <div class="calendar-days">
          <button v-for="cell in cells" :key="cell.date" type="button" :data-date="cell.date" :disabled="disabled || cell.disabled" :aria-label="cell.date" :aria-pressed="cell.date === selected" :aria-current="cell.today ? 'date' : undefined" :class="{ 'is-outside': !cell.inMonth, 'is-selected': cell.date === selected, 'is-today': cell.today }" @keydown="moveFocus($event, cell.date)" @click="choose(cell.date)">{{ cell.day }}</button>
        </div>
        <footer>
          <button type="button" :disabled="disabled || !isCalendarDateAllowed(today, min, max)" @click="choose(today)">Today</button>
          <button v-if="!required" type="button" :disabled="disabled" @click="clearSelection">Clear</button>
          <button type="button" @click="close(true)">{{ confirm ? 'Cancel' : 'Done' }}</button>
          <UiButton v-if="confirm" label="Apply date" :disabled="!canApply" @click="applySelection" />
        </footer>
      </div>
    </details>
  </div>
</template>
