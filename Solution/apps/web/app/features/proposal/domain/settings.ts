import type { ProposalSettings } from '../../../shared/api/contracts/proposal'

export type NumericSettingKey = { [K in keyof ProposalSettings]: ProposalSettings[K] extends number ? K : never }[keyof ProposalSettings]
export type FlagSettingKey = { [K in keyof ProposalSettings]: ProposalSettings[K] extends boolean ? K : never }[keyof ProposalSettings]
export const WORKING_DAYS: readonly { key: FlagSettingKey; label: string }[] = [
  { key: 'workMonday', label: 'Monday' }, { key: 'workTuesday', label: 'Tuesday' },
  { key: 'workWednesday', label: 'Wednesday' }, { key: 'workThursday', label: 'Thursday' },
  { key: 'workFriday', label: 'Friday' }, { key: 'workSaturday', label: 'Saturday' }, { key: 'workSunday', label: 'Sunday' },
]
/** PreZero = given by PreZero on 14 Nov 2026 · Assumption = our value until measured · Planner = tuning of the selection rule. */
export type SettingSource = 'PreZero' | 'Assumption' | 'Planner'
export interface SettingField {
  key: NumericSettingKey; label: string; unit: string; min: number; max: number; step: number
  source: SettingSource; help: string; minExclusive?: boolean; integer?: boolean
}

/** Same defaults as the API (`OperationsSettings`). A request only sends values that differ. */
export const DEFAULT_PROPOSAL_SETTINGS: Readonly<ProposalSettings> = Object.freeze({
  containerVolumeM3: 3, glassDensityKgM3: 350,
  truckPayloadT: 12, truckVolumeM3: 0, maxVehicles: 12,
  shiftHours: 8, fixedTravelMin: 10, avgSpeedKph: 25, detourFactor: 1.3,
  serviceMinPerBin: 5, serviceMinPerStop: 0, unloadMin: 15,
  workSaturday: false, workSunday: false,
  workMonday: true, workTuesday: true, workWednesday: true, workThursday: true, workFriday: true,
  depotLatitude: 49.1427, depotLongitude: 9.2185, disposalLatitude: 49.165, disposalLongitude: 9.235,
  lookaheadDays: 1, mustProbability: 0.7, neighbourProbability: 0.12, neighbourFillPercent: 40, optionalProbability: 0.4,
  vehicleFixedCostMin: 480, optionalValueMin: 15, solverTimeLimitSeconds: 3,
})

export const SETTING_GROUPS: readonly { title: string; fields: readonly SettingField[] }[] = [
  { title: 'Containers and glass', fields: [
    { key: 'containerVolumeM3', label: 'Container volume', unit: 'm³', min: 0, max: 100, step: 0.5, source: 'PreZero', minExclusive: true, help: 'All containers are the same size.' },
    { key: 'glassDensityKgM3', label: 'Glass density', unit: 'kg per m³', min: 0, max: 5000, step: 10, source: 'Assumption', minExclusive: true, help: 'Turns fill level into weight. Replace with weighbridge data when available.' },
  ] },
  { title: 'Trucks', fields: [
    { key: 'truckPayloadT', label: 'Payload per load', unit: 't', min: 0, max: 100, step: 0.5, source: 'PreZero', minExclusive: true, help: 'Weight limit of one load. One truck takes all three glass colours.' },
    { key: 'truckVolumeM3', label: 'Volume per load', unit: 'm³', min: 0, max: 500, step: 1, source: 'Assumption', help: '0 = unknown, only the weight limit applies.' },
    { key: 'maxVehicles', label: 'Trucks available', unit: 'trucks', min: 1, max: 200, step: 1, source: 'PreZero', integer: true, help: 'Upper bound. The plan uses as few as it needs.' },
  ] },
  { title: 'Working time', fields: [
    { key: 'shiftHours', label: 'Shift length', unit: 'hours', min: 0, max: 24, step: 0.5, source: 'PreZero', minExclusive: true, help: 'Includes the last unloading and the drive back.' },
    { key: 'fixedTravelMin', label: 'Driving time between stops', unit: 'minutes', min: 0, max: 600, step: 1, source: 'PreZero', help: 'Used for every drive. 0 = use map coordinates (straight line × detour).' },
    { key: 'serviceMinPerBin', label: 'Time to empty one container', unit: 'minutes', min: 0, max: 240, step: 0.5, source: 'PreZero', help: 'Containers at one site share the drive.' },
    { key: 'serviceMinPerStop', label: 'Extra time per stop', unit: 'minutes', min: 0, max: 240, step: 0.5, source: 'Assumption', help: 'Parking and setup.' },
    { key: 'unloadMin', label: 'Time for one unloading', unit: 'minutes', min: 0, max: 600, step: 1, source: 'Assumption', help: 'Each time a truck is full, and at the end of the day.' },
  ] },
  { title: 'Selection rule', fields: [
    { key: 'lookaheadDays', label: 'Look-ahead', unit: 'collection days', min: 1, max: 14, step: 1, source: 'Planner', integer: true, help: '1 = empty what would overflow before the next collection day.' },
    { key: 'mustProbability', label: 'Overflow risk that makes a stop mandatory', unit: '0 to 1', min: 0, max: 1, step: 0.05, source: 'Planner', help: 'Lower = more cautious: more visits, less overflow.' },
    { key: 'neighbourFillPercent', label: 'Also empty neighbours from this fill', unit: '%', min: 0, max: 100, step: 5, source: 'Planner', help: 'Other containers at a site the truck visits anyway.' },
    { key: 'optionalProbability', label: 'Risk that makes a site optional', unit: '0 to 1', min: 0, max: 1, step: 0.05, source: 'Planner', help: 'Optional sites only use spare time of trucks that drive anyway.' },
    { key: 'neighbourProbability', label: 'Neighbour risk threshold', unit: '0 to 1', min: 0, max: 1, step: 0.01, source: 'Planner', help: 'Also empty a bin at a due site if its risk exceeds this threshold.' },
    { key: 'vehicleFixedCostMin', label: 'Preference for fewer trucks', unit: 'minutes per truck', min: 0, max: 2000, step: 30, source: 'Planner', help: 'Omar’s OR-Tools fixed vehicle cost; discourages opening another truck.' },
    { key: 'optionalValueMin', label: 'Value of optional collection', unit: 'detour minutes', min: 0, max: 600, step: 1, source: 'Planner', help: 'Risk-weighted value used when deciding whether an optional detour is worthwhile.' },
    { key: 'solverTimeLimitSeconds', label: 'Solver time per attempt', unit: 'seconds', min: 1, max: 30, step: 1, integer: true, source: 'Planner', help: 'Longer searches may improve routes. Backtests cap each daily attempt at two seconds.' },
  ] },
  { title: 'Travel and depot assumptions', fields: [
    { key: 'avgSpeedKph', label: 'Average driving speed', unit: 'km/h', min: 0, max: 150, minExclusive: true, step: 1, source: 'Assumption', help: 'Used in coordinate-based travel mode.' },
    { key: 'detourFactor', label: 'Straight-line detour factor', unit: 'multiplier', min: 1, max: 5, step: 0.1, source: 'Assumption', help: 'Does not replace road-network travel times.' },
    { key: 'depotLatitude', label: 'Yard latitude', unit: 'degrees', min: -90, max: 90, step: 0.001, source: 'Assumption', help: 'Placeholder until verified.' },
    { key: 'depotLongitude', label: 'Yard longitude', unit: 'degrees', min: -180, max: 180, step: 0.001, source: 'Assumption', help: 'Placeholder until verified.' },
    { key: 'disposalLatitude', label: 'Unloading-site latitude', unit: 'degrees', min: -90, max: 90, step: 0.001, source: 'Assumption', help: 'Used for intermediate and final unloading.' },
    { key: 'disposalLongitude', label: 'Unloading-site longitude', unit: 'degrees', min: -180, max: 180, step: 0.001, source: 'Assumption', help: 'Used for intermediate and final unloading.' },
  ] },
]
const FIELDS = SETTING_GROUPS.flatMap(group => group.fields)

/** One message per invalid field. Values are never clipped into range. */
export function validateSettings(settings: ProposalSettings): Partial<Record<NumericSettingKey, string>> {
  const errors: Partial<Record<NumericSettingKey, string>> = {}
  for (const field of FIELDS) {
    const value = settings[field.key]
    if (typeof value !== 'number' || !Number.isFinite(value)) errors[field.key] = 'Enter a number.'
    else if (field.integer && !Number.isInteger(value)) errors[field.key] = 'Enter a whole number.'
    else if (value > field.max || (field.minExclusive ? value <= field.min : value < field.min))
      errors[field.key] = `Must be ${field.minExclusive ? 'greater than' : 'at least'} ${field.min} and at most ${field.max}.`
  }
  if (!WORKING_DAYS.some(day => settings[day.key])) errors.lookaheadDays = 'Choose at least one working collection day.'
  return errors
}

/** Query for `/api/proposal`: the history cutoff plus only the values that differ from the defaults. */
export function proposalQuery(asOf: string, settings: ProposalSettings): Record<string, string | number | boolean> {
  const query: Record<string, string | number | boolean> = { asOf }
  for (const key of Object.keys(DEFAULT_PROPOSAL_SETTINGS) as (keyof ProposalSettings)[]) {
    if (settings[key] !== DEFAULT_PROPOSAL_SETTINGS[key]) query[key] = settings[key]
  }
  return query
}
