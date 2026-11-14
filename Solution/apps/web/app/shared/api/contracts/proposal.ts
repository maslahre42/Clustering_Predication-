export type BinDecision = 'due' | 'neighbour' | 'optional' | 'skipped' | 'no_forecast'
export type UnservedReason = 'exceeds_truck_capacity' | 'exceeds_shift' | 'fleet_limit' | 'optional_not_scheduled' | 'missing_coordinates' | 'solver_no_solution'

/** Operating numbers of the proposal. Names match the API query parameters. */
export interface ProposalSettings {
  containerVolumeM3: number; glassDensityKgM3: number
  truckPayloadT: number; truckVolumeM3: number; maxVehicles: number
  shiftHours: number; fixedTravelMin: number; avgSpeedKph: number; detourFactor: number
  serviceMinPerBin: number; serviceMinPerStop: number; unloadMin: number
  workSaturday: boolean; workSunday: boolean
  workMonday: boolean; workTuesday: boolean; workWednesday: boolean; workThursday: boolean; workFriday: boolean
  depotLatitude: number; depotLongitude: number; disposalLatitude: number; disposalLongitude: number
  lookaheadDays: number; mustProbability: number; neighbourProbability: number; neighbourFillPercent: number; optionalProbability: number
  vehicleFixedCostMin: number; optionalValueMin: number; solverTimeLimitSeconds: number
}
export interface ProposalBin {
  locationId: string; material: string; lastEmptied: string; daysSinceEmptied: number
  expectedFillPercent: number | null; overflowProbability: number | null
  decision: BinDecision; volumeL: number; weightKg: number
}
export interface ProposalStop {
  locationId: string; mandatory: boolean; risk: number; bins: number; volumeL: number; weightKg: number
  latitude: number | null; longitude: number | null; materials: string[]
}
export interface ProposalTrip { stops: string[]; weightKg: number; volumeL: number }
export interface ProposalRoute { truck: number; trips: ProposalTrip[]; hours: number; distanceKm: number | null; bins: number }
export interface ProposalUnserved { locationId: string; mandatory: boolean; reason: UnservedReason }
export interface ProposalTotals {
  trucks: number; trips: number; stops: number; bins: number; hours: number; distanceKm: number | null
  weightT: number; volumeM3: number; loadsByCapacity: number
}
export interface ProposalModel {
  bins: number; cycles: number; censoredCycles: number; sigma: number; tau: number
  materialRatePercentPerDay: Record<string, number>
  engine?: string; vacationMultiplier?: number | null; seasonality?: { month: number; multiplier: number }[]
}
/** Forecast, selection and routes for the first collection day after `asOf`. Predictions, not measurements. */
export interface CollectionProposal {
  asOf: string; planDate: string; windowEnd: string; settings: ProposalSettings; model: ProposalModel
  bins: ProposalBin[]; stops: ProposalStop[]
  plan: { routes: ProposalRoute[]; unserved: ProposalUnserved[]; totals: ProposalTotals }
  assumptions: string[]
}
