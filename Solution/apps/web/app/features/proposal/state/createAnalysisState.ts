import { ref, watch, type Ref } from 'vue'
import type { ProposalSettings } from '../../../shared/api/contracts/proposal'
import type { ForecastCurve, SimulationResult } from '../../../shared/api/contracts/simulation'
import type { ProposalDataset } from '../../../shared/api/contracts/comparison'
import { proposalQuery } from '../domain/settings.ts'

type Query = Record<string, string | number | boolean>
interface Transport {
  forecast(query: Query, signal: AbortSignal): Promise<ForecastCurve>
  simulation(query: Query, signal: AbortSignal): Promise<SimulationResult>
}
function previousDate(value: string) {
  const date = new Date(`${value}T00:00:00Z`); date.setUTCDate(date.getUTCDate() - 13)
  return date.toISOString().slice(0, 10)
}
const problem = (error: any) => error?.data?.detail ?? error?.message ?? 'The calculation failed.'

/** Request-local analysis state; changing inputs cancels and invalidates older results. */
export function createAnalysisState(asOf: Ref<string>, settings: Ref<ProposalSettings>, transport: Transport, dataset?: Ref<ProposalDataset | null>) {
  const forecastInput = ref({ locationId: '', material: 'white', horizonDays: 60 })
  const simulationInput = ref({ start: previousDate(asOf.value), end: asOf.value, seed: 7 })
  const forecast = ref<ForecastCurve | null>(null), simulation = ref<SimulationResult | null>(null)
  const forecasting = ref(false), simulating = ref(false)
  const forecastError = ref(''), simulationError = ref('')
  let forecastController: AbortController | undefined, simulationController: AbortController | undefined
  function clearForecast() { forecastController?.abort(); forecast.value = null; forecasting.value = false; forecastError.value = '' }
  function clearSimulation() { simulationController?.abort(); simulation.value = null; simulating.value = false; simulationError.value = '' }
  watch(forecastInput, clearForecast, { deep: true, flush: 'sync' })
  watch(simulationInput, clearSimulation, { deep: true, flush: 'sync' })
  watch(asOf, () => {
    clearForecast(); clearSimulation()
    simulationInput.value = { ...simulationInput.value, start: previousDate(asOf.value), end: asOf.value }
  }, { flush: 'sync' })
  if (dataset) watch(dataset, () => { clearForecast(); clearSimulation(); forecastInput.value.locationId = '' }, { flush: 'sync' })
  watch(settings, () => { clearForecast(); clearSimulation() }, { deep: true, flush: 'sync' })
  async function runForecast() {
    clearForecast()
    if (!forecastInput.value.locationId) { forecastError.value = 'Choose a bin first.'; return }
    const controller = forecastController = new AbortController()
    forecasting.value = true
    try {
      const value = await transport.forecast({ ...proposalQuery(asOf.value, settings.value), ...forecastInput.value }, controller.signal)
      if (!controller.signal.aborted) forecast.value = value
    } catch (error) { if (!controller.signal.aborted) forecastError.value = problem(error) }
    finally { if (!controller.signal.aborted) forecasting.value = false }
  }
  async function runSimulation() {
    clearSimulation()
    const { start, end, seed } = simulationInput.value
    const days = (Date.parse(end) - Date.parse(start)) / 86400000
    if (!Number.isFinite(days) || days < 0 || days > 30 || end > asOf.value || !Number.isInteger(seed) || seed < 0 || seed > 1000000) {
      simulationError.value = 'Choose 1–31 days ending on or before the history cutoff and an integer seed from 0 to 1000000.'; return
    }
    const controller = simulationController = new AbortController()
    simulating.value = true
    try {
      const value = await transport.simulation({ ...proposalQuery(asOf.value, settings.value), start, end, seed }, controller.signal)
      if (!controller.signal.aborted) simulation.value = value
    } catch (error) { if (!controller.signal.aborted) simulationError.value = problem(error) }
    finally { if (!controller.signal.aborted) simulating.value = false }
  }
  function dispose() { clearForecast(); clearSimulation() }
  return { forecastInput, simulationInput, forecast, simulation, forecasting, simulating, forecastError, simulationError,
    runForecast, runSimulation, dispose }
}
