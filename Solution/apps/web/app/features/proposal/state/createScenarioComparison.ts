import { computed, ref, watch, type Ref } from 'vue'
import type { CollectionProposal } from '../../../shared/api/contracts/proposal'
import { compareScenarios } from '../domain/insights.ts'

/** Parent-owned snapshot survives loading the next proposal. Context changes clear it. */
export function createScenarioComparison(current: Ref<CollectionProposal | null | undefined>, context: Ref<string>) {
  const baseline = ref<CollectionProposal | null>(null)
  watch(context, () => { baseline.value = null }, { flush: 'sync' })
  function save() { if (current.value) baseline.value = JSON.parse(JSON.stringify(current.value)) }
  function clear() { baseline.value = null }
  const comparison = computed(() => baseline.value && current.value ? compareScenarios(baseline.value,current.value) : null)
  return { baseline, comparison, save, clear }
}
