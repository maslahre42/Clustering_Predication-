import { ref, type Ref } from 'vue'
import type { DataIssue, ProposalDataset } from '../../../shared/api/contracts/comparison'
import type { DatasetValidation } from '../../../shared/api/contracts/dataset'
export interface CsvFile { name: string; size: number; text(): Promise<string> }
interface ImportOptions {
  metadata?: Ref<DatasetValidation | null>
  validate?: (csv: string, signal: AbortSignal) => Promise<DatasetValidation>
}

/** Selected files activate only after validation; rejected/stale imports preserve the active source. */
export function createProposalDataset(selected: Ref<ProposalDataset | null>, options: ImportOptions = {}) {
  const error = ref(''), reading = ref(false), phase = ref(''), dragging = ref(false), issues = ref<DataIssue[]>([])
  let revision = 0, dragDepth = 0, controller: AbortController | undefined
  function cancel() { revision++; controller?.abort(); reading.value = false; phase.value = ''; dragDepth = 0; dragging.value = false }
  async function load(file: CsvFile) {
    cancel()
    const version = revision
    error.value = ''; issues.value = []
    if (!/\.csv$/i.test(file.name)) { error.value = 'Choose a file with a .csv extension.'; return }
    if (file.size > 2_000_000) { error.value = 'Choose a CSV file of at most 2 MB.'; return }
    reading.value = true; phase.value = 'Reading your file…'
    const request = controller = new AbortController()
    try {
      const csv = await file.text()
      if (version !== revision) return
      if (!csv.trim()) { error.value = 'The selected file is empty.'; return }
      phase.value = 'Checking columns and collection records…'
      const metadata = options.validate ? await options.validate(csv, request.signal) : null
      if (version !== revision || request.signal.aborted) return
      if (options.metadata) options.metadata.value = metadata
      selected.value = { name: file.name, csv }
    } catch (failure: any) {
      if (version !== revision || request.signal.aborted) return
      issues.value = failure?.data?.validation?.errors ?? []
      error.value = issues.value.length ? 'Some collection records need fixing. Review the rows below.' : failure?.data?.detail ?? (options.validate ? 'We could not validate this file. Check your connection and try again.' : 'The file could not be read.')
    } finally { if (version === revision) { reading.value = false; phase.value = '' } }
  }
  function receiveFiles(files: ArrayLike<CsvFile> | null | undefined) {
    if (!files?.length) return
    if (files.length !== 1) { cancel(); issues.value = []; error.value = 'Drop one CSV file at a time.'; return }
    return load(files[0]!)
  }
  function dragEnter(types: readonly string[]) { if (types.includes('Files')) { dragDepth++; dragging.value = true } }
  function dragLeave() { dragDepth = Math.max(0, dragDepth - 1); dragging.value = dragDepth > 0 }
  function drop(files: ArrayLike<CsvFile> | null | undefined) { dragDepth = 0; dragging.value = false; return receiveFiles(files) }
  function clear() { cancel(); selected.value = null; if (options.metadata) options.metadata.value = null; error.value = ''; issues.value = [] }
  return { load, clear, cancel, dispose: cancel, receiveFiles, dragEnter, dragLeave, drop, error, issues, phase, reading, dragging }
}
