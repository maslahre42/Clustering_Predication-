export interface FillDistribution { low0To30: number; midAbove30Below70: number; high70Below100: number; full100: number; overfull: number; unknown: number }
export interface MaterialAnalytics { material: string; collections: number; numericReadings: number; overfullCount: number; unknownCount: number; meanNumericFill: number | null; medianIntervalDays: number | null; intervalCount: number; distribution: FillDistribution }
export interface MonthlyAnalytics { month: string; material: string; collections: number; overfullCount: number; numericReadings: number; meanNumericFill: number | null }
export interface MaterialCyclePattern { material: string; numericCycles: number; lowerBoundCycles: number; medianRatePercentPerDay: number | null }
export interface ReviewBin { locationId: string; material: string; collections: number; lowCollections: number; overfullCollections: number; reason: 'repeated_overfull' | 'frequent_low_fill' }
export interface CollectionPatterns { firstDate: string | null; lastDate: string | null; cycles: MaterialCyclePattern[]; reviewBinCount: number; reviewBins: ReviewBin[] }
export interface CollectionAnalytics { asOf: string; totalCollections: number; knownBins: number; binsWithFewerThan3Readings: number; overfullCount: number; materials: MaterialAnalytics[]; months: MonthlyAnalytics[]; patterns: CollectionPatterns }
