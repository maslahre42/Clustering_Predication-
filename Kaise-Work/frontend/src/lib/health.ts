export interface Health {
  status: string;
}

/** Calls the backend liveness probe via the Vite dev-server proxy. */
export async function fetchHealth(): Promise<Health> {
  const response = await fetch("/health");
  if (!response.ok) {
    throw new Error(`GET /health failed: ${response.status}`);
  }
  return (await response.json()) as Health;
}
