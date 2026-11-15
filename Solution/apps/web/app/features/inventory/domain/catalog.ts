import type { Location } from '../../../shared/api/contracts/locations'
import type { PlanningSnapshot } from '../../../shared/api/contracts/planning'
import type { PlanningBin } from '../types'
export interface LocationCluster<T extends PlanningBin = PlanningBin> { locationId: string; latitude: number; longitude: number; bins: T[]; isSynthetic: boolean }
export function knownBins(snapshot: PlanningSnapshot | null | undefined, locations: Location[], asOf: string): PlanningBin[] {
  if (!snapshot || snapshot.asOf !== asOf) return []
  const coordinates = new Map(locations.map(l => [l.locationId, l]))
  return snapshot.bins.filter(b => b.lastCollection <= asOf).flatMap(bin => {
    const location = coordinates.get(bin.locationId)
    return location ? [{ ...bin, key: `${bin.locationId}:${bin.material}`, name: `Location ${bin.locationId.slice(0, 8)}`, latitude: location.latitude, longitude: location.longitude, isSynthetic: location.isSynthetic }] : []
  })
}
export function clusterBins<T extends PlanningBin>(bins: T[]): LocationCluster<T>[] {
  const clusters = new Map<string, LocationCluster<T>>()
  for (const bin of bins) {
    if (!clusters.has(bin.locationId)) clusters.set(bin.locationId, { locationId: bin.locationId, latitude: bin.latitude, longitude: bin.longitude, isSynthetic: bin.isSynthetic, bins: [] })
    clusters.get(bin.locationId)!.bins.push(bin)
  }
  return [...clusters.values()]
}
