import { DEFAULT_PROPOSAL_SETTINGS } from '../../apps/web/app/features/proposal/domain/settings.ts'

/** A small, hand-checkable proposal: one truck, two loads, one optional stop left out. */
const bin = (locationId, material, decision, fill, risk) => ({ locationId, material, lastEmptied: '2026-08-03', daysSinceEmptied: 14,
  expectedFillPercent: fill, overflowProbability: risk, decision, volumeL: decision === 'skipped' ? 0 : fill * 30, weightKg: decision === 'skipped' ? 0 : fill * 10.5 })
const stop = (locationId, mandatory, risk, materials, weightKg) => ({ locationId, mandatory, risk, bins: materials.length, volumeL: weightKg / 0.35, weightKg, latitude: 49.15, longitude: 9.22, materials })
export function sampleProposal() {
  return {
    routing: { provider: 'Test road service', profile: 'driving', distanceSource: 'street-network', objective: 'driving-distance', assignment: 'compact-sectors', note: 'Fixture only' },
    asOf: '2026-08-14', planDate: '2026-08-17', windowEnd: '2026-08-18', settings: { ...DEFAULT_PROPOSAL_SETTINGS },
    model: { bins: 7, cycles: 60, censoredCycles: 12, sigma: 0.6, tau: 0.65, materialRatePercentPerDay: { brown: 0.7, green: 2, white: 3 } },
    bins: [
      bin('A', 'white', 'due', 96, 0.91), bin('A', 'green', 'neighbour', 55, 0.2), bin('A', 'brown', 'skipped', 12, 0.01),
      bin('B', 'white', 'due', 90, 0.75), bin('C', 'green', 'optional', 70, 0.45), bin('D', 'white', 'optional', 80, 0.6),
      { ...bin('E', 'brown', 'no_forecast', null, null), expectedFillPercent: null, overflowProbability: null },
    ],
    stops: [stop('A', true, 0.91, ['green', 'white'], 1585.5), stop('B', true, 0.75, ['white'], 945), stop('C', false, 0.45, ['green'], 735), stop('D', false, 0.6, ['white'], 840)],
    plan: {
      routes: [{ truck: 1, trips: [{ stops: ['B', 'A'], weightKg: 2530.5, volumeL: 7230 }, { stops: ['D'], weightKg: 840, volumeL: 2400 }], hours: 1.75, distanceKm: 12.5, bins: 4, territory: 'Sector 1', roadPaths: [
        { load: 1, returning: false, points: [[49.1427,9.2185],[49.145,9.219],[49.15,9.22],[49.16,9.23],[49.165,9.235]], distanceKm: 6, drivingSeconds: 800 },
        { load: 2, returning: false, points: [[49.165,9.235],[49.16,9.23],[49.15,9.22],[49.165,9.235]], distanceKm: 4, drivingSeconds: 600 },
        { load: 2, returning: true, points: [[49.165,9.235],[49.15,9.225],[49.1427,9.2185]], distanceKm: 2.5, drivingSeconds: 400 },
      ] }],
      unserved: [{ locationId: 'C', mandatory: false, reason: 'optional_not_scheduled' }],
      totals: { trucks: 1, trips: 2, stops: 3, bins: 4, hours: 1.75, distanceKm: null, weightT: 3.3705, volumeM3: 9.63, loadsByCapacity: 1 },
    },
    assumptions: ['Glass density is an assumption.'],
  }
}
