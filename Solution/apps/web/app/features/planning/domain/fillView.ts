import type { PlanningBin } from '../../inventory/types'
import type { SelectedDayFill } from '../../../shared/api/contracts/planning'

export type PlanningFillView = 'estimate' | 'recorded'
export interface PlanningViewBin extends PlanningBin {
  fillView: PlanningFillView; viewDate: string; viewFillPercent: number | null; viewIsOverfull: boolean
  viewState: 'recorded' | 'emptied' | 'estimated' | 'unknown' | 'loading'; lower: number | null; upper: number | null
}
const validFill = (value: number | null | undefined): value is number => value != null && Number.isFinite(value) && value >= 0 && value <= 100

/** Recorded evidence is immutable. Selected-day state never falls back to a stale full reading. */
export function planningViewBins(bins: PlanningBin[], asOf: string, view: PlanningFillView, state?: SelectedDayFill | null, pending = false, error?: unknown): PlanningViewBin[] {
  const matched = !error && !pending && state?.asOf === asOf && state.semantics === 'after-recorded-emptyings'
  const states = new Map((matched ? state.bins : []).map(bin => [JSON.stringify([bin.locationId,bin.material]),bin]))
  return bins.map(bin => {
    if (view === 'recorded') return {...bin,fillView:view,viewDate:bin.lastCollection,viewFillPercent:bin.lastFillPercent,viewIsOverfull:!!bin.lastIsOverfull,viewState:'recorded',lower:null,upper:null}
    const current = states.get(JSON.stringify([bin.locationId,bin.material]))
    const result: PlanningViewBin = {...bin,fillView:view,viewDate:asOf,viewFillPercent:null,viewIsOverfull:false,viewState:pending&&!error?'loading':'unknown',lower:null,upper:null}
    if (!current || current.lastEmptied !== bin.lastCollection || !validFill(current.expectedFillPercent)) return result
    const reset = current.status === 'emptied' && current.lastEmptied === asOf && current.expectedFillPercent === 0
    const estimated = current.status === 'estimated' && current.lastEmptied < asOf
    if (!reset && !estimated) return result
    return {...result,viewFillPercent:current.expectedFillPercent,viewState:reset?'emptied':'estimated',
      lower:validFill(current.lower)?current.lower:null,upper:validFill(current.upper)?current.upper:null}
  })
}
export function planningFillLabel(bin?: PlanningViewBin): string {
  if (!bin) return 'Unknown'
  if (bin.fillView === 'recorded') return bin.viewIsOverfull ? 'Overfull' : bin.viewFillPercent == null ? 'Unknown' : `${bin.viewFillPercent}%`
  if (bin.viewState === 'loading') return 'Estimating…'
  if (bin.viewState === 'emptied') return '0% · emptied'
  return bin.viewFillPercent == null ? 'Unknown' : `~${bin.viewFillPercent.toFixed(1)}%`
}
