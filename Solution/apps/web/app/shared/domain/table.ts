export type TableSortDirection = 'asc' | 'desc'

/** Sort a copy, keeping missing statistics last in either direction. */
export function sortTableRows<T>(rows: readonly T[], value: (row: T) => string | number | null | undefined, direction: TableSortDirection): T[] {
  return [...rows].sort((a, b) => {
    const left = value(a), right = value(b)
    if (left == null) return right == null ? 0 : 1
    if (right == null) return -1
    const comparison = typeof left === 'number' && typeof right === 'number'
      ? left - right
      : String(left).localeCompare(String(right), 'en')
    return direction === 'asc' ? comparison : -comparison
  })
}
