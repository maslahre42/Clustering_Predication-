export interface DatasetDateRange {
  firstDate: string | null
  lastDate: string | null
  maxPlanningDate: string | null
}

export interface DatasetValidation {
  source: 'uploaded-csv'
  fingerprint: string
  rows: number
  locations: number
  bins: number
  firstDate: string | null
  lastDate: string | null
  materials: Record<'brown' | 'green' | 'white', number>
  warnings: import('./comparison').DataIssue[]
}
