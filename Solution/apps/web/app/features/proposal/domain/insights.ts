import type { CollectionProposal, BinFillTiming } from '../../../shared/api/contracts/proposal'

export const euro = (value: number | null | undefined) => value == null ? 'Not priced' : new Intl.NumberFormat('en-IE', { style: 'currency', currency: 'EUR' }).format(value)
export function timingRows(rows: BinFillTiming[], search: string, material: string) {
  const term = search.trim().toLowerCase()
  return rows.filter(row => (!material || row.material === material) && `${row.locationId} ${row.material}`.toLowerCase().includes(term))
    .sort((a,b) => (a.medianDaysUntilFull ?? Infinity) - (b.medianDaysUntilFull ?? Infinity) || a.locationId.localeCompare(b.locationId) || a.material.localeCompare(b.material))
}
export function daysLabel(days: number | null) {
  if (days == null) return 'Insufficient history'
  if (days < 0) return `${Math.abs(days).toFixed(1)} days past estimate`
  return `${days.toFixed(1)} days`
}
export const missedUrgent = (proposal: CollectionProposal) => proposal.plan.unserved.filter(stop => stop.mandatory).length
function servedBins(proposal: CollectionProposal) {
  const served = new Set(proposal.plan.routes.flatMap(route => route.trips.flatMap(trip => trip.stops)))
  return proposal.bins.filter(bin => served.has(bin.locationId) && ['due','neighbour','optional'].includes(bin.decision)).map(bin => JSON.stringify([bin.locationId,bin.material])).sort().join('|')
}
/** A smaller route only counts as a saving when inputs and completed service match. */
export function compareScenarios(baseline: CollectionProposal, current: CollectionProposal) {
  const reasons: string[] = []
  if (!baseline.dataset?.fingerprint || baseline.dataset.fingerprint !== current.dataset?.fingerprint || baseline.asOf !== current.asOf || baseline.planDate !== current.planDate || baseline.windowEnd !== current.windowEnd) reasons.push('Data or planning dates differ.')
  if (missedUrgent(baseline) || missedUrgent(current)) reasons.push('At least one plan misses urgent collections.')
  if (servedBins(baseline) !== servedBins(current)) reasons.push('The plans collect different containers.')
  const fixedInputs = ['containerVolumeM3','glassDensityKgM3','serviceMinPerBin','serviceMinPerStop','unloadMin','depotLatitude','depotLongitude','disposalLatitude','disposalLongitude'] as const
  if (fixedInputs.some(key => baseline.settings[key] !== current.settings[key])) reasons.push('Physical or service assumptions differ.')
  if (!baseline.routing || !current.routing || baseline.routing.distanceSource !== 'street-network' || current.routing.distanceSource !== 'street-network' || baseline.routing.provider !== current.routing.provider || baseline.routing.profile !== current.routing.profile) reasons.push('Street-distance sources differ or are unavailable.')
  const samePrices = baseline.settings.costPerKmEuro === current.settings.costPerKmEuro && baseline.settings.fixedTruckCostEuro === current.settings.fixedTruckCostEuro
  if (!samePrices) reasons.push('Operating prices differ.')
  const comparable = reasons.length === 0
  const before = baseline.costs?.totalEuro, after = current.costs?.totalEuro
  return { comparable, reasons, savedKm: comparable && baseline.plan.totals.distanceKm != null && current.plan.totals.distanceKm != null ? baseline.plan.totals.distanceKm-current.plan.totals.distanceKm : null,
    savedEuro: comparable && before != null && after != null ? Math.round((before-after)*100)/100 : null }
}
export const PRESENTATION_SLIDES = ['The collection challenge', 'When containers may become full', 'Coordinated street routes', 'Operating costs', 'Scenario and service trade-offs', 'Evidence and hand-off']
export const nextSlide = (current: number, delta: number) => Math.max(0, Math.min(PRESENTATION_SLIDES.length-1,current+delta))
