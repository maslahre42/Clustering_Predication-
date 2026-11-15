import { ref, watch, type Ref } from 'vue'
import type { CapacityResult, CapacityScenarioInput, GlassType } from '../../../shared/api/contracts/capacity'
import type { ProposalSettings } from '../../../shared/api/contracts/proposal'
import type { ProposalDataset } from '../../../shared/api/contracts/comparison'
import { capacityDefaults, capacityErrors } from '../domain/capacity.ts'
import { proposalQuery } from '../domain/settings.ts'

export interface CapacityPlanningCache { context: string; input: CapacityScenarioInput; result: CapacityResult }

export function createCapacityPlanning(asOf: Ref<string>, settings: Ref<ProposalSettings>, dataset: Ref<ProposalDataset | null>, dirty: Ref<boolean>,
  transport: (query: Record<string, string | number | boolean>, body: CapacityScenarioInput & { csv?: string }, signal: AbortSignal) => Promise<CapacityResult>, cache?: Ref<CapacityPlanningCache | null>) {
  const input = ref(capacityDefaults()), result = ref<CapacityResult | null>(null), pending = ref(false), error = ref('')
  const context = () => JSON.stringify([asOf.value,settings.value,dataset.value?.csv ?? null])
  if (cache?.value && cache.value.context === context() && !dirty.value) {
    input.value = JSON.parse(JSON.stringify(cache.value.input))
    result.value = cache.value.result
  } else if (cache) cache.value = null
  let controller: AbortController | undefined
  function invalidate() { controller?.abort(); result.value = null; pending.value = false; error.value = ''; if (cache) cache.value = null }
  watch([input, settings, asOf, dataset, dirty], invalidate, { deep: true, flush: 'sync' })
  function addOverride(locationId: string, material: GlassType, known: { locationId: string; material: string }[]) {
    if (!known.some(b => b.locationId === locationId && b.material === material) || input.value.overrides.some(r => r.locationId === locationId && r.material === material)) return false
    input.value.overrides.push({ locationId, material, baselineCount: input.value.baselineContainers[material], alternativeCount: input.value.alternativeContainers[material] })
    return true
  }
  function setSiteLimit(locationId: string, maxContainers: number) {
    if (!locationId || !Number.isInteger(maxContainers) || maxContainers < 1 || maxContainers > 60) return false
    const existing = input.value.siteLimits.find(r => r.locationId === locationId)
    if (existing) existing.maxContainers = maxContainers
    else input.value.siteLimits.push({ locationId, maxContainers })
    return true
  }
  async function run(optimize = false) {
    invalidate()
    if (dirty.value) { error.value = 'Apply collection settings first.'; return }
    const problems = capacityErrors({ ...input.value, optimize })
    if (problems.length) { error.value = problems.join(' '); return }
    const request = controller = new AbortController()
    pending.value = true
    const body = JSON.parse(JSON.stringify(input.value)) as CapacityScenarioInput & { csv?: string }
    body.optimize = optimize
    if (dataset.value) body.csv = dataset.value.csv
    try {
      const value = await transport(proposalQuery(asOf.value, settings.value), body, request.signal)
      if (!request.signal.aborted) {
        result.value = value
        if (cache) cache.value = { context: context(), input: JSON.parse(JSON.stringify(input.value)), result: value }
      }
    } catch (failure: any) {
      if (!request.signal.aborted) error.value = failure?.data?.validation?.errors?.map((r: { message: string }) => r.message).join(' ') || failure?.data?.detail || failure?.message || 'Scenario comparison unavailable.'
    } finally { if (!request.signal.aborted) pending.value = false }
  }
  return { input, result, pending, error, addOverride, setSiteLimit, run, dispose: () => { controller?.abort(); pending.value = false } }
}
