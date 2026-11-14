export function isIsoDate(value: string | null | undefined): value is string {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith('0000')) return false
  const timestamp = Date.parse(`${value}T00:00:00Z`)
  return Number.isFinite(timestamp) && new Date(timestamp).toISOString().slice(0, 10) === value
}

/** Calendar widgets use local dates; API cutoffs are timezone-free service days. */
export function isoDateToLocalDate(value: string | null | undefined): Date | undefined {
  if (!isIsoDate(value)) return undefined
  const [year, month, day] = value.split('-').map(Number)
  const date = new Date(0)
  date.setFullYear(year!, month! - 1, day!)
  date.setHours(0, 0, 0, 0)
  return date
}

export function localDateToIsoDate(value: Date | null | undefined): string | undefined {
  if (!value || !Number.isFinite(value.getTime())) return undefined
  const date = `${String(value.getFullYear()).padStart(4, '0')}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`
  return isIsoDate(date) ? date : undefined
}
