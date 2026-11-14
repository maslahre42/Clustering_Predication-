import { computed, toValue, type MaybeRefOrGetter } from 'vue'
import type { CollectionProposal, ProposalSettings } from '~/shared/api/contracts/proposal'
import type { ProposalDataset } from '~/shared/api/contracts/comparison'
import { API_ROUTES } from '~/shared/api/routes'
import { proposalQuery } from '../domain/settings'

/** Nuxt adapter: refetches when the history cutoff or the applied settings change. */
export function useCollectionProposal(asOf: MaybeRefOrGetter<string>, settings: MaybeRefOrGetter<ProposalSettings>, dataset: MaybeRefOrGetter<ProposalDataset | null>) {
  const query = computed(() => proposalQuery(toValue(asOf), toValue(settings)))
  const method = computed(() => toValue(dataset) ? 'POST' as const : 'GET' as const)
  const body = computed(() => toValue(dataset) ? { csv: toValue(dataset)!.csv } : undefined)
  const request = useFetch<CollectionProposal>(API_ROUTES.proposal, { query, method, body, timeout: 240000 })
  const ready = computed(() => request.status.value !== 'pending' && !request.error.value && request.data.value?.asOf === toValue(asOf))
  const problem = computed(() => (request.error.value?.data as { detail?: string } | undefined)?.detail ?? '')
  return { ...request, ready, problem }
}
