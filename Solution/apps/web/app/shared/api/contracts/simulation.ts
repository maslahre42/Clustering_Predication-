import type { DatasetEvidence, ForecastComparison, OptimizationCheck } from './comparison'
import type { ProposalSettings } from './proposal'
export interface ForecastCurve {
  asOf: string; locationId: string; material: string; lastEmptied: string; medianDaysToFull: number; note: string
  history: { date: string; fill: number | null; isOverfull: boolean }[]
  points: { date: string; expectedFill: number; lower: number; upper: number; risk: number }[]
}
export interface SimulationDaily { date: string; stops: number; bins: number; hours?: number; trucks?: number; dropped_mandatory?: number }
export interface SimulationScenario {
  name: string; label: string; site_visits: number; bin_collections: number; mean_fill_at_collection_pct: number
  share_collections_below_40pct: number; overflow_bin_days: number; overflow_events: number
  hours: number; truckDays: number; missedMandatory: number; daily: SimulationDaily[]
}
export interface SimulationResult {
  asOf: string; start: string; end: string; seed: number; knownBins: number; trainingCycles: number; trainingThrough: string
  dataset: DatasetEvidence; forecastComparison: ForecastComparison; optimizationCheck: OptimizationCheck
  settings: ProposalSettings; effectiveSolverTimeSeconds: number; scenarios: SimulationScenario[]; assumptions: string[]
  frontier: { threshold: number; site_visits: number; overflow_bin_days: number; overflow_events: number }[]
}
