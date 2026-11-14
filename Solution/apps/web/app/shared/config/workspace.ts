import type { Point } from '../domain/geometry'
export interface WorkspaceConfiguration {
  depot: Point & { isSynthetic: boolean; name: string }
}
// A replaceable preview configuration, not a confirmed operational depot.
export const DEFAULT_WORKSPACE: WorkspaceConfiguration = {
  depot: { latitude: 49.1427, longitude: 9.2185, isSynthetic: true, name: 'City center' },
}
