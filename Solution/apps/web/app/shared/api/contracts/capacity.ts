import type { ProposalSettings, ProposalRoute, ProposalStop, CollectionProposal } from './proposal'
export type GlassType = 'brown' | 'green' | 'white'
export interface ContainerOverride { locationId: string; material: GlassType; baselineCount: number; alternativeCount: number }
export interface CapacityScenarioInput {
  optimize: boolean
  optimizationWeeks: number
  targetFillPercent: number
  maxContainersPerType: number
  maxContainersPerSite: number
  minIntervalDays: number
  maxIntervalDays: number
  siteLimits: { locationId: string; maxContainers: number }[]
  days: number
  baselineIntervalDays: number
  alternativeIntervalDays: number
  baselineContainers: Record<GlassType, number>
  alternativeContainers: Record<GlassType, number>
  containerCostPerMonthEuro: number
  overrides: ContainerOverride[]
}
export interface CapacityCost {
  drivingIncluded?: boolean
  configured: boolean; partial: boolean
  truckEuro: number | null; roadEuro: number | null; containerEuro: number | null
  totalEuro: number | null; monthlyEquivalentEuro: number | null
}
export interface CapacityScenario {
  name: 'baseline' | 'alternative'; intervalDays: number | null; installedContainers: number
  truckDays: number; peakTrucks: number; distanceKm: number; workingHours: number; emptyingHours: number
  containersEmptied: number; siteVisits: number; demandLitres: number; collectedLitres: number
  remainingLitres: number; spillLitres: number; fullStreamDays: number; pendingSites: number; pendingSiteDays: number
  costs: CapacityCost
  feasible?: boolean; targetViolationStreamDays?: number; cyclicStockStable?: boolean
  averageFillAtCollection?: number | null
  daily: { routes?: ProposalRoute[]; stops?: (Omit<ProposalStop, 'risk'> & { risk: number | null })[]; date: string; truckDays: number; distanceKm: number; hours: number; containersEmptied: number; siteVisits: number; pendingSites: number; spillLitres: number }[]
}
export interface CapacityResult {
  settings?: ProposalSettings; routing?: CollectionProposal['routing']; optimization?: JointOptimization
  asOf: string; start: string; end: string; days: number; supportedStreams: number
  excludedStreams: { locationId: string; material: GlassType }[]; missingCoordinateSites: string[]
  comparableService: boolean
  fillingTimes: { material: GlassType; supportedStreams: number; positiveStreams: number; zeroDemandStreams: number; historicalCycles: number; baselineAverageDays: number | null; alternativeAverageDays: number | null }[]
  scenarios: CapacityScenario[]; assumptions: string[]
}

export interface JointRecommendation {
  locationId: string; material: GlassType; baselineCount: number; recommendedCount: number
  dailyLitres: number; averageIntervalDays: number | null; maximumIntervalDays: number | null
  visits: number; maximumFillPercent: number
}
export interface JointCollection { date: string; locationId: string; material: GlassType; containers: number; fillPercent: number; volumeL: number }
export interface JointOptimization {
  status: 'best-feasible-found' | 'no-feasible-plan-found'; globalOptimalityProven: boolean
  targetFillPercent: number; candidatesEvaluated: number; geometryError: string | null
  recommendations: JointRecommendation[]; collections: JointCollection[]
  search: { strategy: string; status: string; proxyOnly: boolean }[]
}
