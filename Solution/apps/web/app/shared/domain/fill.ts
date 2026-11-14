interface HistoricalFill { lastFillPercent: number | null; lastIsOverfull?: boolean }
export function historicalFillState(value: number | null | undefined, overfull = false): 'low' | 'high' | 'full' | 'overfull' | 'unknown' {
  if (overfull) return 'overfull'
  if (value == null || !Number.isFinite(value) || value < 0 || value > 100) return 'unknown'
  if (value === 100) return 'full'
  return value >= 70 ? 'high' : 'low'
}
export function matchesHistoricalFill(bin: HistoricalFill, minimum: number): boolean {
  return !!bin.lastIsOverfull || minimum === 0 || (bin.lastFillPercent !== null && bin.lastFillPercent >= minimum)
}
export function historicalFillLabel(value: number | null | undefined, overfull = false): string {
  return overfull ? 'Overfull' : value == null ? 'Unknown' : `${value}%`
}
export function historicalFillRank(bin: HistoricalFill): number {
  // An ordering sentinel only; never exported or used as a measured percentage.
  return bin.lastIsOverfull ? Number.POSITIVE_INFINITY : bin.lastFillPercent ?? -1
}
