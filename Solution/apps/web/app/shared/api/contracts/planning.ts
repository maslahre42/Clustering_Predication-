export interface BinSummary { locationId: string; material: string; lastCollection: string; lastFillPercent: number | null; collections: number; lastIsOverfull?: boolean }
export interface PlanningSnapshot { asOf: string; observationCount: number; firstDate: string | null; lastDate: string | null; bins: BinSummary[] }
