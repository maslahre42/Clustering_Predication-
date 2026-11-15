import type { ReactNode } from "react";

/** Shared panel shell: titled, bordered section used across the dashboard. */
export function Panel({
  title,
  subtitle,
  children,
  testid,
}: {
  title: string;
  subtitle?: ReactNode;
  children: ReactNode;
  testid?: string;
}) {
  return (
    <section
      className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
      data-testid={testid}
    >
      <h2 className="text-base font-semibold text-slate-900">{title}</h2>
      {subtitle ? <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p> : null}
      <div className="mt-3">{children}</div>
    </section>
  );
}
