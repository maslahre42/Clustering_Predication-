import type { MonthlyAnalytics } from '../../../shared/api/contracts/analytics'
import { monthCoverage } from './patterns.ts'

export function monthlyDashboard(source: MonthlyAnalytics[], asOf: string, firstDate?: string | null) {
  const rows = source.filter(row => row.month <= asOf.slice(0, 7))
  const months = [...new Set(rows.map(row => row.month))].sort()
  const colors: Record<string, string> = { white: '#4887bd', green: '#299b42', brown: '#925b4d' }
  const x = (index: number) => 50 + (index + .5) * 580 / Math.max(1, months.length)
  const charts = [
    { title: 'Monthly collections', unit: 'Containers emptied', kind: 'bar', keys: ['white', 'green', 'brown'], thresholds: [] as number[], value: (row: MonthlyAnalytics) => row.collections },
    { title: 'Active collection days', unit: 'Days with at least one collection', kind: 'bar', keys: ['white', 'green', 'brown'], thresholds: [] as number[], value: (row: MonthlyAnalytics) => row.activeDays ?? null },
    { title: 'Mean fill at truck arrival', unit: 'Numeric mean fill (%)', kind: 'line', keys: ['white', 'green', 'brown'], thresholds: [40, 80], value: (row: MonthlyAnalytics) => row.meanNumericFill },
    { title: 'Full white glass & premature brown collections', unit: 'Share of all monthly collections (%)', kind: 'line', keys: ['white', 'brown'], thresholds: [50], value: (row: MonthlyAnalytics) => {
      const count = row.material === 'white' ? row.fullOrOverfullCount : row.prematureCount
      return count == null || !row.collections ? null : count / row.collections * 100
    } },
  ].map((chart, chartIndex) => {
    const series = chart.keys.map((key, seriesIndex) => {
      const points = months.map((month, index) => {
        const row = rows.find(row => row.month === month && row.material === key)
        return { month, value: row ? chart.value(row) : null, x: x(index) }
      })
      return { key, color: chartIndex === 3 && key === 'white' ? '#e57a19' : colors[key], label: chartIndex === 3 ? key === 'white' ? 'White ≥100% / overfull' : 'Brown <40%' : key[0]!.toUpperCase() + key.slice(1), seriesIndex, points }
    })
    const maximum = chartIndex >= 2 ? 100 : Math.max(1, ...series.flatMap(s => s.points.map(p => p.value ?? 0)))
    const y = (value: number) => 240 - value / maximum * 190
    const barWidth = Math.min(24, 580 / Math.max(1, months.length) / 4)
    return { ...chart, maximum, barWidth, ticks: Array.from({ length: 5 }, (_, i) => ({ value: maximum * i / 4, y: y(maximum * i / 4) })),
      guides: chart.thresholds.map(value => ({ value, y: y(value) })),
      series: series.map(s => ({ ...s, points: s.points.map(p => ({ ...p, y: p.value == null ? null : y(p.value), barX: p.x + (s.seriesIndex - 1.5) * barWidth })),
        path: s.points.map((p, i) => p.value == null ? '' : `${i === 0 || s.points[i - 1]?.value == null ? 'M' : 'L'}${p.x},${y(p.value)}`).join(' ') })) }
  })
  return { charts, months: months.map((month, i) => ({ month, x: x(i), coverage: monthCoverage(month, asOf, firstDate) })) }
}
