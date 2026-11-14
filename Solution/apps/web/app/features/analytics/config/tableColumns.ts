import type { MonthlyAnalytics } from '../../../shared/api/contracts/analytics'

export type MaterialColumn = 'material' | 'collections' | 'overfullCount' | 'meanNumericFill' | 'medianIntervalDays' | 'low' | 'unknownCount'
export type MonthlyColumn = keyof MonthlyAnalytics

export const MATERIAL_COLUMNS: readonly { field: MaterialColumn; label: string }[] = [
  { field: 'material', label: 'Glass' },
  { field: 'collections', label: 'Collections' },
  { field: 'overfullCount', label: 'Overfull at collection' },
  { field: 'meanNumericFill', label: 'Mean numeric fill' },
  { field: 'medianIntervalDays', label: 'Median interval' },
  { field: 'low', label: 'Readings ≤30%' },
  { field: 'unknownCount', label: 'Unknown' },
]

export const MONTHLY_COLUMNS: readonly { field: MonthlyColumn; label: string }[] = [
  { field: 'month', label: 'Month' },
  { field: 'material', label: 'Glass' },
  { field: 'collections', label: 'Collections' },
  { field: 'overfullCount', label: 'Overfull' },
  { field: 'meanNumericFill', label: 'Numeric mean fill' },
]
