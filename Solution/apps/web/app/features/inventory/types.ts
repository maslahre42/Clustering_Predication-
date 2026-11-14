import type { BinSummary } from '../../shared/api/contracts/planning'
export interface PlanningBin extends BinSummary {
  key: string
  name: string
  latitude: number
  longitude: number
  isSynthetic: boolean
}
