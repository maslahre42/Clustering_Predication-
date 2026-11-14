import { computed, ref } from 'vue'
import type { ProposalSettings } from '../../../shared/api/contracts/proposal'
import { DEFAULT_PROPOSAL_SETTINGS, validateSettings, type FlagSettingKey, type NumericSettingKey } from '../domain/settings.ts'

/** Edits are a draft. Only a valid, applied draft changes the request, so half-typed numbers never reach the API. */
export function createProposalSettings(initial: ProposalSettings = DEFAULT_PROPOSAL_SETTINGS) {
  const draft = ref<ProposalSettings>({ ...initial })
  const applied = ref<ProposalSettings>({ ...initial })
  const errors = computed(() => validateSettings(draft.value))
  const valid = computed(() => Object.keys(errors.value).length === 0)
  const keys = Object.keys(DEFAULT_PROPOSAL_SETTINGS) as (keyof ProposalSettings)[]
  const dirty = computed(() => keys.some(key => !Object.is(draft.value[key], applied.value[key])))
  /** Applied values that differ from the defaults. */
  const changed = computed(() => keys.filter(key => applied.value[key] !== DEFAULT_PROPOSAL_SETTINGS[key]))

  function setNumber(key: NumericSettingKey, raw: string) {
    const text = raw.trim().replace(',', '.')
    draft.value = { ...draft.value, [key]: text === '' ? Number.NaN : Number(text) }
  }
  function setFlag(key: FlagSettingKey, value: boolean) { draft.value = { ...draft.value, [key]: value } }
  function apply() {
    if (!valid.value) return false
    applied.value = { ...draft.value }
    return true
  }
  function discard() { draft.value = { ...applied.value } }
  function reset() { draft.value = { ...DEFAULT_PROPOSAL_SETTINGS }; applied.value = { ...DEFAULT_PROPOSAL_SETTINGS } }
  return { draft, applied, errors, valid, dirty, changed, setNumber, setFlag, apply, discard, reset }
}
