import type { TableSortDirection } from '../../domain/table'

export const HISTORY_PAGE_SIZE = 50

export interface Observation { locationId: string; material: string; date: string; fillLevelPercent: number | null; isOverfull?: boolean }
export interface HistoryPage { total: number; page: number; pageSize: number; items: Observation[] }

export type HistorySortField = 'date' | 'location' | 'material' | 'fill'
export type SortDirection = TableSortDirection
