import { ref, type Ref } from 'vue'
import type { ProposalDataset } from '../../../shared/api/contracts/comparison'

/** Request-local upload selection. Validation runs on the server before any model uses it. */
export function createProposalDataset(selected: Ref<ProposalDataset | null>) {
  const error = ref(''), reading = ref(false)
  let revision = 0
  async function load(file: { name: string; size: number; text(): Promise<string> }) {
    const version = ++revision
    error.value = ''; reading.value = false
    if (file.size > 2_000_000) { error.value = 'Choose a CSV file of at most 2 MB.'; return }
    reading.value = true
    try {
      const csv = await file.text()
      if (version !== revision) return
      if (!csv.trim()) { error.value = 'The selected file is empty.'; return }
      selected.value = { name: file.name, csv }
    } catch { if (version === revision) error.value = 'The file could not be read.' }
    finally { if (version === revision) reading.value = false }
  }
  function clear() { revision++; selected.value = null; error.value = ''; reading.value = false }
  return { load, clear, error, reading }
}
