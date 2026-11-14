export interface Point { latitude: number; longitude: number }
export function distanceKm(a: Point, b: Point): number {
  const rad = Math.PI / 180
  const dlat = (b.latitude - a.latitude) * rad
  const dlon = (b.longitude - a.longitude) * rad
  const h = Math.sin(dlat / 2) ** 2 + Math.cos(a.latitude * rad) * Math.cos(b.latitude * rad) * Math.sin(dlon / 2) ** 2
  return 6371 * 2 * Math.asin(Math.sqrt(Math.min(1, h)))
}
export function orderStops<T extends Point>(stops: T[], depot: Point): T[] {
  const remaining = [...stops]
  const result: T[] = []
  let previous: Point = depot
  while (remaining.length) {
    let closest = 0
    for (let i = 1; i < remaining.length; i++) {
      if (distanceKm(previous, remaining[i]!) < distanceKm(previous, remaining[closest]!)) closest = i
    }
    const next = remaining.splice(closest, 1)[0]!
    result.push(next)
    previous = next
  }
  return result
}

// All selected glass bins at a location share one physical collection stop.
export function groupStops<T extends Point & { locationId: string }>(bins: T[]): T[] {
  const locations = new Map<string, T>()
  for (const bin of bins) {
    if (!locations.has(bin.locationId)) locations.set(bin.locationId, bin)
  }
  return [...locations.values()]
}

export function roundTripKm(stops: Point[], depot: Point): number {
  if (!stops.length) return 0
  const points = [depot, ...stops, depot]
  return points.slice(1).reduce((sum, point, i) => sum + distanceKm(points[i]!, point), 0)
}
