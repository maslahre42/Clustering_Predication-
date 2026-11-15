import type { MonthlyAnalytics } from '../../../shared/api/contracts/analytics'

/** Describe available calendar coverage; absence of visits never implies zero fill. */
export function monthCoverage(month: string, asOf: string, firstDate?: string | null): string | null {
  const [year, number] = month.split('-').map(Number)
  if (!year || !number || number > 12) return null
  const first = `${month}-01`
  const last = `${month}-${new Date(Date.UTC(year, number, 0)).getUTCDate()}`
  const start = firstDate && firstDate > first && firstDate <= last ? firstDate : first
  const end = asOf < last ? asOf : last
  return start > first || end < last ? `Partial · ${start}–${end}` : null
}

export function monthlyTrend(months: MonthlyAnalytics[], material: string, asOf: string, firstDate?: string | null) {
  const rows = months.filter(row => row.material === material && row.month <= asOf.slice(0, 7))
    .sort((a, b) => a.month.localeCompare(b.month))
  return rows.map(row => ({ ...row, coverage: monthCoverage(row.month, asOf, firstDate) }))
}
