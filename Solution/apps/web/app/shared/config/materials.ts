export const GLASS_MATERIALS = ['brown', 'green', 'white'] as const
export const GLASS_OPTIONS = GLASS_MATERIALS.map(value => ({ value, label: `${value} glass` }))
