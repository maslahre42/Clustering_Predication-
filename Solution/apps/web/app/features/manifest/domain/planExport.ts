import type { LocationCluster } from '../../inventory/domain/catalog'
export function csvCell(value: unknown): string {
  return `"${String(value ?? '').replaceAll('"', '""')}"`
}
export function planCsv(asOf: string, stops: LocationCluster[], notes: Record<string, string>): string {
  const rows = [['planning_date', 'stop', 'location_id', 'material', 'last_collection', 'pre_emptying_fill_percent', 'was_overfull', 'latitude', 'longitude', 'synthetic_coordinates', 'collector_note'],
    ...stops.flatMap((stop, i) => stop.bins.map(bin => [asOf, i + 1, stop.locationId, bin.material, bin.lastCollection, bin.lastFillPercent ?? '', !!bin.lastIsOverfull, stop.latitude, stop.longitude, stop.isSynthetic, notes[stop.locationId] ?? '']))]
  return rows.map(row => row.map(csvCell).join(',')).join('\r\n')
}

