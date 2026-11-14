interface CoordinateProvenance { isSynthetic: boolean }
export function coordinateSourceLabel(locations: readonly CoordinateProvenance[]): string {
  if (!locations.length) return 'No locations'
  const synthetic = locations.filter(location => location.isSynthetic).length
  if (synthetic === locations.length) return 'Synthetic coordinates'
  return synthetic === 0 ? 'Imported coordinates' : 'Mixed coordinate sources'
}
