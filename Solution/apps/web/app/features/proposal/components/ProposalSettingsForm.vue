<script setup lang="ts">
import { ref } from 'vue';
import type { ProposalSettings } from '~/shared/api/contracts/proposal';
import { SETTING_GROUPS, WORKING_DAYS, type FlagSettingKey, type NumericSettingKey } from '~/features/proposal/domain/settings';

const props = defineProps<{
  settings: ProposalSettings;
  errors: Partial<Record<NumericSettingKey, string>>;
  dirty: boolean;
}>();
const emit = defineEmits<{
  number: [key: NumericSettingKey, raw: string];
  flag: [key: FlagSettingKey, value: boolean];
  apply: [];
  reset: [];
}>();
// Keep what the person typed ("1," or an empty field) instead of re-rendering the parsed number over it.
const typed = ref<Partial<Record<NumericSettingKey, string>>>({});
const shown = (key: NumericSettingKey) => typed.value[key] ?? (Number.isFinite(props.settings[key]) ? String(props.settings[key]) : '');
function edit(key: NumericSettingKey, raw: string) { typed.value = { ...typed.value, [key]: raw }; emit('number', key, raw); }
function finish(event: 'apply' | 'reset') { typed.value = {}; if (event === 'apply') emit('apply'); else emit('reset'); }
const hasErrors = () => Object.keys(props.errors).length > 0;
</script>
<template>
  <UiCard class="proposal-settings">
    <h2>Operating numbers</h2>
    <p>Every number is editable. <strong>PreZero</strong> values were given by PreZero, <strong>Assumption</strong> values are ours until measured, <strong>Planner</strong> values tune the selection rule.</p>
    <fieldset v-for="group in SETTING_GROUPS" :key="group.title">
      <legend>{{ group.title }}</legend>
      <div class="proposal-settings-grid">
        <div v-for="field in group.fields" :key="field.key" class="proposal-setting">
          <UiInput :model-value="shown(field.key)" :label="`${field.label} (${field.unit})`" type="text" density="compact" @update:model-value="edit(field.key, $event)" />
          <UiTag :label="field.source" :color="field.source === 'PreZero' ? 'success' : 'neutral'" density="compact" />
          <small v-if="errors[field.key]" class="proposal-setting-error" role="alert">{{ errors[field.key] }}</small>
          <small v-else>{{ field.help }}</small>
        </div>
      </div>
    </fieldset>
    <fieldset>
      <legend>Collection days</legend>
      <p>Defaults: Monday to Friday (PreZero). Adjust the service calendar for this scenario.</p>
      <UiCheckbox v-for="day in WORKING_DAYS" :key="day.key" :model-value="settings[day.key]" :label="day.label" @update:model-value="emit('flag', day.key, $event)" />
    </fieldset>
    <div class="proposal-settings-actions">
      <UiButton label="Apply and recalculate" :disabled="hasErrors() || !dirty" @click="finish('apply')" />
      <UiButton label="Reset to defaults" mode="outline" @click="finish('reset')" />
    </div>
  </UiCard>
</template>
