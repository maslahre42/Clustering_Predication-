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

/** Public road-routing defaults match the API. Travel distances and times come from the street network. */
export const DEFAULT_PROPOSAL_SETTINGS: Readonly<ProposalSettings> = Object.freeze({
  containerVolumeM3: 3, glassDensityKgM3: 350,
  truckPayloadT: 12, truckVolumeM3: 0, maxVehicles: 12,
  brownCompartmentM3: 0, greenCompartmentM3: 0, whiteCompartmentM3: 0,
  costPerKmEuro: 0, fixedTruckCostEuro: 500,
  shiftHours: 8,
  serviceMinPerBin: 5, serviceMinPerStop: 0, unloadMin: 15,
  workSaturday: false, workSunday: false,
  workMonday: true, workTuesday: true, workWednesday: true, workThursday: true, workFriday: true,
  depotLatitude: 49.0094, depotLongitude: 8.4044, disposalLatitude: 49.0094, disposalLongitude: 8.4044,
  lookaheadDays: 1, mustProbability: 0.7, neighbourProbability: 0.12, neighbourFillPercent: 40, optionalProbability: 0.4,
  optionalValueMin: 0, solverTimeLimitSeconds: 3,
})

export const SETTING_GROUPS: readonly { title: string; fields: readonly SettingField[] }[] = [
  { title: 'Containers and glass', fields: [
    { key: 'containerVolumeM3', label: 'Container volume', unit: 'm³', min: 0, max: 100, step: 0.5, source: 'PreZero', minExclusive: true, help: 'All containers are the same size.' },
    { key: 'glassDensityKgM3', label: 'Glass density', unit: 'kg per m³', min: 0, max: 5000, step: 10, source: 'Assumption', minExclusive: true, help: 'Turns fill level into weight. Replace with weighbridge data when available.' },
  ] },
  { title: 'Trucks', fields: [
    { key: 'truckPayloadT', label: 'Payload per load', unit: 't', min: 0, max: 100, step: 0.5, source: 'PreZero', minExclusive: true, help: 'Weight limit of one load. One truck takes all three glass colours.' },
    { key: 'truckVolumeM3', label: 'Volume per load', unit: 'm³', min: 0, max: 500, step: 1, source: 'Assumption', help: '0 = no separate total-volume limit. Configured glass compartments and payload still apply.' },
    { key: 'maxVehicles', label: 'Trucks available', unit: 'trucks', min: 1, max: 200, step: 1, source: 'PreZero', integer: true, help: 'Upper bound. The plan uses as few as it needs.' },
  ] },
  { title: 'Working time', fields: [
    { key: 'shiftHours', label: 'Shift length', unit: 'hours', min: 0, max: 24, step: 0.5, source: 'PreZero', minExclusive: true, help: 'Includes the last unloading and the drive back.' },
    { key: 'serviceMinPerBin', label: 'Time to empty one container', unit: 'minutes', min: 0, max: 240, step: 0.5, source: 'PreZero', help: 'Containers at one site share the drive.' },
    { key: 'serviceMinPerStop', label: 'Extra time per stop', unit: 'minutes', min: 0, max: 240, step: 0.5, source: 'Assumption', help: 'Parking and setup.' },
    { key: 'unloadMin', label: 'Time for one unloading', unit: 'minutes', min: 0, max: 600, step: 1, source: 'Assumption', help: 'Each time a truck is full, and at the end of the day.' },
  ] },
  { title: 'Glass compartments', fields: [
    { key: 'brownCompartmentM3', label: 'Brown glass compartment', unit: 'm³', min: 0, max: 500, step: 0.5, source: 'Assumption', help: 'Enter the actual capacity for each glass color. All zero means the layout is unknown; no equal split is assumed.' },
    { key: 'greenCompartmentM3', label: 'Green glass compartment', unit: 'm³', min: 0, max: 500, step: 0.5, source: 'Assumption', help: 'A full green compartment requires unloading even if other compartments have space.' },
    { key: 'whiteCompartmentM3', label: 'White glass compartment', unit: 'm³', min: 0, max: 500, step: 0.5, source: 'Assumption', help: 'Configure all three compartments together. All colors unload at the disposal site.' },
  ] },
  { title: 'Operating costs', fields: [
    { key: 'costPerKmEuro', label: 'Additional distance charge', unit: '€ per km', min: 0, max: 1000, step: 0.01, source: 'Assumption', help: 'Driving kilometres are included in the €500 truck-day package. Leave zero. Enter a positive rate only for an additional charge outside that package.' },
    { key: 'fixedTruckCostEuro', label: 'Truck-day package', unit: '€ per truck', min: 0, max: 100000, step: 1, source: 'PreZero', help: 'Provider: €500 per truck-day includes truck, driver and driving kilometres. Counted once per scheduled day, including multiple unloading loads.' },
  ] },
  { title: 'Selection rule', fields: [
    { key: 'lookaheadDays', label: 'Look-ahead', unit: 'collection days', min: 1, max: 14, step: 1, source: 'Planner', integer: true, help: '1 = empty what would overflow before the next collection day.' },
    { key: 'mustProbability', label: 'Overflow risk that makes a stop mandatory', unit: '0 to 1', min: 0, max: 1, step: 0.05, source: 'Planner', help: 'Lower = more cautious: more visits, less overflow.' },
    { key: 'neighbourFillPercent', label: 'Also empty neighbours from this fill', unit: '%', min: 0, max: 100, step: 5, source: 'Planner', help: 'Other containers at a site the truck visits anyway.' },
    { key: 'optionalProbability', label: 'Risk that makes a site optional', unit: '0 to 1', min: 0, max: 1, step: 0.05, source: 'Planner', help: 'Optional sites only use spare time of trucks that drive anyway.' },
    { key: 'neighbourProbability', label: 'Neighbour risk threshold', unit: '0 to 1', min: 0, max: 1, step: 0.01, source: 'Planner', help: 'Also empty a bin at a due site if its risk exceeds this threshold.' },
    { key: 'optionalValueMin', label: 'Optional collection value', unit: 'minutes equivalent', min: 0, max: 600, step: 1, source: 'Planner', help: 'Default 0: avoid added driving for non-urgent sites. A higher value explicitly trades extra road kilometers for earlier service.' },
    { key: 'solverTimeLimitSeconds', label: 'Solver time per attempt', unit: 'seconds', min: 1, max: 30, step: 1, integer: true, source: 'Planner', help: 'Longer searches may improve routes. Backtests cap each daily attempt at two seconds.' },
  ] },
  { title: 'Travel and depot assumptions', fields: [
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
  const compartments = ['brownCompartmentM3', 'greenCompartmentM3', 'whiteCompartmentM3'] as const
  if (compartments.some(key => settings[key] > 0)) {
    for (const key of compartments) if (settings[key] < .001) errors[key] = 'Enter at least 0.001 m³ for each compartment, or leave all three zero.'
    if (settings.truckVolumeM3 > 0 && compartments.reduce((sum, key) => sum + settings[key], 0) > settings.truckVolumeM3 + 1e-9)
      errors.truckVolumeM3 = 'Total truck volume must cover all three compartments.'
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
