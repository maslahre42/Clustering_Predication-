/** Keep table navigation bounded even for a large historical dataset. */
export function paginationItems(current: number, total: number): (number | '…')[] {
  const count = Math.max(1, Math.floor(total))
  const page = Math.max(1, Math.min(count, Math.floor(current)))
  const visible = new Set([1, count, page - 1, page, page + 1].filter(value => value >= 1 && value <= count))
  if (page <= 3) for (let n = 1; n <= Math.min(4, count); n++) visible.add(n)
  if (page >= count - 2) for (let n = Math.max(1, count - 3); n <= count; n++) visible.add(n)
  const result: (number | '…')[] = []
  for (const n of [...visible].sort((a, b) => a - b)) {
    const previous = result.at(-1)
    if (typeof previous === 'number' && n - previous > 1) result.push('…')
    result.push(n)
  }
  return result
}
