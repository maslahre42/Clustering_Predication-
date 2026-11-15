export interface DataIssue { rule_id: string; row_number: number; message: string; value?: string | null }
export interface DatasetEvidence {
  source: 'sqlite-snapshot' | 'uploaded-csv'; fingerprint: string; rows: number; bins: number
  dateMin: string | null; dateMax: string | null; unknown: number; overfull: number; warnings: DataIssue[]
  grouping: { method: string; gate: Record<string, boolean>; silhouetteByK: Record<string, number>; eligible: number; insufficient: number
    profiles: { label: string; n_series: number; feature_medians: Record<string, number | null> }[]
    labels: { locationId: string; material: string; group: string }[]; note: string }
}
export interface ForecastComparison {
  targets: number; evaluated: number; commonNumericCases: number; commonCensoredCases: number; unknownTargets: number; note: string
  models: { name: string; label: string; available: number; mae: number | null; bias: number | null; lowerBoundShortfall: number | null }[]
}
export interface OptimizationCheck {
  status: string; message: string; scope: string; date: string; sites: string[]; complete: boolean
  fleetLowerBound?: number; trucks?: number; runtimeSeconds?: number; note?: string
  routes?: { truck: string; sites: string[]; volumeM3: number; weightKg: number; hours: number; distanceKm: number | null }[]
  unserved?: { Location_id: string; reason: string }[]
}
export interface ProposalDataset { name: string; csv: string }
