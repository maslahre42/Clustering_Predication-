import type { BinDecision, CollectionProposal, ProposalBin, UnservedReason } from '../../../shared/api/contracts/proposal'
import { csvCell } from '../../manifest/domain/planExport.ts'

export const DECISION_LABELS: Record<BinDecision, string> = {
  due: 'Must empty', neighbour: 'Emptied on the way', optional: 'If time allows', skipped: 'Not needed yet', no_forecast: 'No forecast',
}
export const DECISION_HELP: Record<BinDecision, string> = {
  due: 'Likely to overflow before the next collection day.',
  neighbour: 'Not urgent, but the truck is at this site anyway.',
  optional: 'Some risk, nothing urgent at the site. Served only with spare time.',
  skipped: 'Low risk and low fill.',
  no_forecast: 'No usable history through the cutoff.',
}
export const REASON_LABELS: Record<UnservedReason, string> = {
  exceeds_truck_capacity: 'Larger than one truck load',
  exceeds_shift: 'Cannot be served within one shift',
  fleet_limit: 'All available trucks are full',
  optional_not_scheduled: 'Optional: no spare time',
  missing_coordinates: 'No coordinates for this site',
  solver_no_solution: 'The solver found no feasible route within its budget',
  road_unreachable: 'No nearby connected driving access',
  sector_limit: 'Not scheduled within sector, shift and search limits',
  exceeds_compartment_capacity: 'A glass compartment is too small for this pickup',
  material_demand_unknown: 'Glass-specific load volumes are unavailable',
}
const COLLECTED: readonly BinDecision[] = ['due', 'neighbour', 'optional']
const isCollected = (bin: ProposalBin) => COLLECTED.includes(bin.decision)

export interface RouteRow {
  truck: number; load: number; sequence: number; locationId: string; mandatory: boolean
  materials: string[]; bins: number; weightKg: number; risk: number
}
/** One row per served stop, in driving order. `sequence` counts stops per truck across its loads. */
export function routeRows(proposal: CollectionProposal): RouteRow[] {
  const stops = new Map(proposal.stops.map(stop => [stop.locationId, stop]))
  return proposal.plan.routes.flatMap(route => {
    let sequence = 0
    return route.trips.flatMap((trip, tripIndex) => trip.stops.flatMap(locationId => {
      const stop = stops.get(locationId)
      return stop ? [{ truck: route.truck, load: tripIndex + 1, sequence: ++sequence, locationId, mandatory: stop.mandatory,
        materials: stop.materials, bins: stop.bins, weightKg: stop.weightKg, risk: stop.risk }] : []
    }))
  })
}
export function servedOrder(proposal: CollectionProposal): string[] {
  return proposal.plan.routes.flatMap(route => route.trips.flatMap(trip => trip.stops))
}
/** Keys (`location:material`) of the bins that are emptied at served stops, in route order. */
export function servedBinKeys(proposal: CollectionProposal): string[] {
  return servedOrder(proposal).flatMap(locationId => proposal.bins
    .filter(bin => bin.locationId === locationId && isCollected(bin)).map(bin => `${bin.locationId}:${bin.material}`))
}
export function proposalSummary(proposal: CollectionProposal) {
  const count = (decision: BinDecision) => proposal.bins.filter(bin => bin.decision === decision).length
  return {
    due: count('due'), neighbour: count('neighbour'), optional: count('optional'), skipped: count('skipped'), noForecast: count('no_forecast'),
    mandatoryStops: proposal.stops.filter(stop => stop.mandatory).length,
    optionalStops: proposal.stops.filter(stop => !stop.mandatory).length,
    unservedMandatory: proposal.plan.unserved.filter(stop => stop.mandatory).length,
    unservedOptional: proposal.plan.unserved.filter(stop => !stop.mandatory).length,
  }
}
/** Bins by overflow risk, highest first. Bins without a forecast come last. */
export function topRisks(proposal: CollectionProposal, limit = Number.POSITIVE_INFINITY): ProposalBin[] {
  return [...proposal.bins].sort((a, b) => (b.overflowProbability ?? -1) - (a.overflowProbability ?? -1)
    || (b.expectedFillPercent ?? -1) - (a.expectedFillPercent ?? -1)
    || a.locationId.localeCompare(b.locationId) || a.material.localeCompare(b.material)).slice(0, limit)
}
/** Collector route sheet: one line per emptied bin, in driving order. Fill and risk are forecasts. */
export function proposalCsv(proposal: CollectionProposal): string {
  const rows: unknown[][] = [['plan_date', 'truck', 'load', 'stop', 'location_id', 'material', 'decision', 'expected_fill_percent', 'overflow_probability', 'estimated_weight_kg', 'last_emptied', 'history_through']]
  for (const row of routeRows(proposal)) {
    for (const bin of proposal.bins.filter(bin => bin.locationId === row.locationId && isCollected(bin))) {
      rows.push([proposal.planDate, row.truck, row.load, row.sequence, bin.locationId, bin.material, bin.decision,
        bin.expectedFillPercent?.toFixed(1) ?? '', bin.overflowProbability?.toFixed(2) ?? '', Math.round(bin.weightKg), bin.lastEmptied, proposal.asOf])
    }
  }
  return rows.map(row => row.map(csvCell).join(',')).join('\r\n')
}
export function formatHours(hours: number): string {
  const minutes = Math.round(hours * 60)
  return minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)} h ${String(minutes % 60).padStart(2, '0')} min`
}
export const formatPercent = (value: number | null | undefined) => value == null ? '—' : `${Math.round(value)}%`
export const formatRisk = (value: number | null | undefined) => value == null ? '—' : `${Math.round(value * 100)}%`
