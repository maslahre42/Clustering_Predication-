import type { CapacityScenarioInput, CapacityResult } from '../../../shared/api/contracts/capacity'
export const CAPACITY_MATERIALS = ['brown', 'green', 'white'] as const
export function capacityDefaults(): CapacityScenarioInput {
  return { optimize: false, optimizationWeeks: 4, targetFillPercent: 90, maxContainersPerType: 3, maxContainersPerSite: 9, minIntervalDays: 1, maxIntervalDays: 28, siteLimits: [], days: 28, baselineIntervalDays: 7, alternativeIntervalDays: 14,
    baselineContainers: { brown: 1, green: 1, white: 1 }, alternativeContainers: { brown: 1, green: 1, white: 1 },
    containerCostPerMonthEuro: 0, overrides: [] }
}
export function capacityErrors(input: CapacityScenarioInput): string[] {
  const errors: string[] = []
  const integer = (n: number, a: number, b: number) => Number.isInteger(n) && n >= a && n <= b
  if (!integer(input.days, 7, 31)) errors.push('Choose 7–31 comparison days.')
  if (![input.baselineIntervalDays, input.alternativeIntervalDays].every(n => integer(n, 1, 28))) errors.push('Collection intervals must be 1–28 calendar days.')
  if (![input.baselineContainers, input.alternativeContainers].every(counts => CAPACITY_MATERIALS.every(m => integer(counts[m], 1, 20)))) errors.push('Enter 1–20 containers per site and glass type.')
  if (!Number.isFinite(input.containerCostPerMonthEuro) || input.containerCostPerMonthEuro < 0 || input.containerCostPerMonthEuro > 10000) errors.push('Container cost must be €0–10,000 per month; zero is unpriced.')
  if (input.optimize) {
    if (!integer(input.optimizationWeeks, 1, 8)) errors.push('Choose a 1–8 week repeating cycle.')
    if (!Number.isFinite(input.targetFillPercent) || input.targetFillPercent < 50 || input.targetFillPercent > 100) errors.push('Fill target must be 50–100%.')
    if (!integer(input.maxContainersPerType, 1, 20) || !integer(input.maxContainersPerSite, 1, 60)) errors.push('Use valid per-type and per-site container limits.')
    if (!integer(input.minIntervalDays, 1, 56) || !integer(input.maxIntervalDays, 1, 56) || input.minIntervalDays > Math.min(input.maxIntervalDays, input.optimizationWeeks * 7)) errors.push('Interval bounds must fit the repeating cycle.')
    const sites = new Set<string>()
    for (const row of input.siteLimits) {
      if (!row.locationId || !integer(row.maxContainers, 1, 60) || sites.has(row.locationId)) errors.push('Site limits must be unique and between 1 and 60.')
      sites.add(row.locationId)
    }
  }
  const seen = new Set<string>()
  for (const row of input.overrides) {
    const key = `${row.locationId}:${row.material}`
    if (!row.locationId || !CAPACITY_MATERIALS.includes(row.material) || !integer(row.baselineCount, 1, 20) || !integer(row.alternativeCount, 1, 20) || seen.has(key)) errors.push('Site overrides must be unique with counts of 1–20.')
    seen.add(key)
  }
  return errors
}
export function capacityCostDifference(result: CapacityResult): number | null {
  const [a, b] = result.scenarios
  return a?.costs.totalEuro != null && b?.costs.totalEuro != null ? b.costs.totalEuro - a.costs.totalEuro : null
}

export function jointPlanCsv(result: CapacityResult): string {
  const scenario = result.scenarios[1]
  const events = result.optimization?.collections ?? []
  const rows: (string | number)[][] = [['date','truck','load','stop','location_id','material','containers','fill_percent','volume_l']]
  for (const day of scenario?.daily ?? []) for (const route of day.routes ?? []) {
    let sequence = 0
    route.trips.forEach((trip, i) => { for (const site of trip.stops) {
      sequence++
      for (const event of events.filter(e => e.date === day.date && e.locationId === site)) rows.push([day.date,route.truck,i+1,sequence,site,event.material,event.containers,event.fillPercent.toFixed(1),event.volumeL.toFixed(1)])
    } })
  }
  return rows.map(row => row.map(v => `"${String(v).replaceAll('"','""')}"`).join(',')).join('\r\n')
}
