import { isIsoDate } from './dates.ts'

export function calendarInitialDate(value: string | null | undefined, min: string | undefined, max: string | undefined, today: string): string {
  let date = isIsoDate(value) ? value : today
  if (min && date < min) date = min
  if (max && date > max) date = max
  return date
}

export function shiftCalendarDate(value: string, days: number): string {
  if (!isIsoDate(value)) throw new Error('Invalid calendar date')
  const date = new Date(`${value}T12:00:00Z`)
  date.setUTCDate(date.getUTCDate() + days)
  const result = date.toISOString().slice(0, 10)
  return isIsoDate(result) ? result : value
}

export function shiftCalendarMonth(month: string, amount: number): string {
  if (!isIsoDate(`${month}-01`)) throw new Error('Invalid calendar month')
  const date = new Date(`${month}-01T12:00:00Z`)
  date.setUTCMonth(date.getUTCMonth() + amount)
  const result = date.toISOString().slice(0, 7)
  return isIsoDate(`${result}-01`) ? result : month
}

export function isCalendarDateAllowed(value: string, min?: string, max?: string): boolean {
  return isIsoDate(value) && (!min || value >= min) && (!max || value <= max)
}

export function calendarCells(month: string, min?: string, max?: string, today?: string) {
  const first = `${month}-01`
  if (!isIsoDate(first)) return []
  const offset = (new Date(`${first}T12:00:00Z`).getUTCDay() + 6) % 7
  return Array.from({ length: 42 }, (_, index) => {
    const date = shiftCalendarDate(first, index - offset)
    return { date, day: Number(date.slice(8)), inMonth: date.startsWith(month), disabled: !isCalendarDateAllowed(date, min, max), today: date === today }
  })
}
