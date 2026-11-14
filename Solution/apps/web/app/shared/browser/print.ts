/** Render the actual generation time before opening the browser print dialog. */
export async function printDatedDocument(
  effects: { setTimestamp: (value: string) => void; afterRender: () => Promise<unknown>; print: () => void },
  now: () => Date = () => new Date(),
): Promise<void> {
  effects.setTimestamp(now().toISOString())
  await effects.afterRender()
  effects.print()
}
