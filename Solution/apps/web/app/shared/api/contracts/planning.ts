export interface BinSummary { locationId: string; material: string; lastCollection: string; lastFillPercent: number | null; collections: number; lastIsOverfull?: boolean }
export interface PlanningSnapshot { asOf: string; observationCount: number; firstDate: string | null; lastDate: string | null; bins: BinSummary[] }

export interface SelectedDayBin { locationId: string; material: string; lastEmptied: string; daysSinceEmptied: number; expectedFillPercent: number | null; lower: number | null; upper: number | null; status: 'emptied' | 'estimated' | 'unknown' }
export interface SelectedDayFill { asOf: string; semantics: 'after-recorded-emptyings'; lastObservationDate: string | null; bins: SelectedDayBin[]; note: string }
