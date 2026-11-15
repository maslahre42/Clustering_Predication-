import type { CollectionProposal } from '../../../shared/api/contracts/proposal'
import type { Location } from '../../../shared/api/contracts/locations'
import { REASON_LABELS } from './proposal.ts'

const COLORS = ['#087f48', '#3568d4', '#a347ba', '#ce7325', '#087f91', '#c14764', '#776629']
export interface MapPoint { latitude: number; longitude: number }
export interface RouteMapStop extends MapPoint {
  key: string; locationId: string; truck: number; load: number; sequence: number; color: string
  materials: string[]; weightKg: number; risk: number; mandatory: boolean
  provenance: 'synthetic' | 'imported' | 'unverified'
}
export interface MapPath { load: number; points: MapPoint[]; returning: boolean }
export interface MapTruck {
  truck: number; color: string; hours: number; loads: number; bins: number; stopCount: number
  weightKg: number; stops: RouteMapStop[]; paths: MapPath[]; missing: number; territory?: string
}
export interface RouteMapModel {
  trucks: MapTruck[]; yard: MapPoint | null; disposal: MapPoint | null
  unserved: (MapPoint & { locationId: string; reason: string; mandatory: boolean })[]
}
export function mapPoint(latitude: number | null | undefined, longitude: number | null | undefined): MapPoint | null {
  return latitude != null && longitude != null && Number.isFinite(latitude) && Number.isFinite(longitude)
    && Math.abs(latitude) <= 90 && Math.abs(longitude) <= 180 ? { latitude, longitude } : null
}

/** Render only returned street geometry. Stop order never becomes invented straight-line geometry. */
export function proposalMap(proposal: CollectionProposal, locations: readonly Location[] = []): RouteMapModel {
  const yard = mapPoint(proposal.routing?.yard?.roadLatitude ?? proposal.settings.depotLatitude, proposal.routing?.yard?.roadLongitude ?? proposal.settings.depotLongitude)
  const disposal = mapPoint(proposal.routing?.disposal?.roadLatitude ?? proposal.settings.disposalLatitude, proposal.routing?.disposal?.roadLongitude ?? proposal.settings.disposalLongitude)
  const inventory = new Map(locations.map(location => [location.locationId, location]))
  const stops = new Map(proposal.stops.map(stop => [stop.locationId, stop]))
  const trucks = proposal.plan.routes.map((route, index) => {
    const color = COLORS[index % COLORS.length]!
    const mapped: RouteMapStop[] = []
    let sequence = 0, missing = 0
    route.trips.forEach((trip, tripIndex) => {
      for (const locationId of trip.stops) {
        sequence++
        const stop = stops.get(locationId), point = stop && mapPoint(stop.roadLatitude ?? stop.latitude, stop.roadLongitude ?? stop.longitude)
        if (!point || !stop) { missing++; continue }
        const known = inventory.get(locationId)
        const same = known && known.latitude === stop.latitude && known.longitude === stop.longitude
        mapped.push({ ...point, key: `${route.truck}:${tripIndex + 1}:${sequence}`, locationId, truck: route.truck,
          load: tripIndex + 1, sequence, color, materials: stop.materials, weightKg: stop.weightKg,
          risk: stop.risk, mandatory: stop.mandatory, provenance: same ? known.isSynthetic ? 'synthetic' : 'imported' : 'unverified' })
      }
    })
    const paths = (route.roadPaths ?? []).flatMap(path => {
      const points = path.points.map(([lat, lon]) => mapPoint(lat, lon))
      return points.length > 1 && points.every((point): point is MapPoint => point != null)
        ? [{ load: path.load, returning: path.returning, points }] : []
    })
    return { truck: route.truck, color, hours: route.hours, loads: route.trips.length, bins: route.bins,
      stopCount: sequence, weightKg: route.trips.reduce((total, trip) => total + trip.weightKg, 0), stops: mapped, paths, missing, territory: route.territory }
  })
  const unserved = proposal.plan.unserved.flatMap(item => {
    const stop = stops.get(item.locationId), point = stop && mapPoint(stop.latitude, stop.longitude)
    return point ? [{ ...point, locationId: item.locationId, reason: REASON_LABELS[item.reason], mandatory: item.mandatory }] : []
  })
  return { trucks, yard, disposal, unserved }
}
