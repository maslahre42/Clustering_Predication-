import { computed, toValue, type MaybeRefOrGetter } from 'vue'
import type { CollectionProposal, ProposalSettings } from '~/shared/api/contracts/proposal'
import { API_ROUTES } from '~/shared/api/routes'
import { proposalQuery } from '../domain/settings'

/** Nuxt adapter: refetches when the history cutoff or the applied settings change. */
export function useCollectionProposal(asOf: MaybeRefOrGetter<string>, settings: MaybeRefOrGetter<ProposalSettings>) {
  const query = computed(() => proposalQuery(toValue(asOf), toValue(settings)))
  const request = useFetch<CollectionProposal>(API_ROUTES.proposal, { query })
  const ready = computed(() => !request.error.value && request.data.value?.asOf === toValue(asOf))
  const problem = computed(() => (request.error.value?.data as { detail?: string } | undefined)?.detail ?? '')
  return { ...request, ready, problem }
}
