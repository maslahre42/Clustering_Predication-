import type { Point } from '../domain/geometry'
export interface WorkspaceConfiguration {
  depot: Point & { isSynthetic: boolean; name: string }
}
// A replaceable preview configuration, not a confirmed operational depot.
export const DEFAULT_WORKSPACE: WorkspaceConfiguration = {
  depot: { latitude: 49.0094, longitude: 8.4044, isSynthetic: true, name: 'City center' },
}
