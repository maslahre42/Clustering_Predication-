import type { ReactNode } from "react";

/**
 * Collapsible "Technical details" block (M11 jury-usability pass): solver
 * statuses, provenance and raw metrics move in here so the main screens stay
 * plain-language. Uses native <details> — children stay in the DOM when
 * collapsed (accessible, testable), just not visible.
 */
export function TechDetails({
  label,
  children,
  testid = "tech-details",
}: {
  label: string;
  children: ReactNode;
  testid?: string;
}) {
  return (
    <details
      className="rounded border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600"
      data-testid={testid}
    >
      <summary className="cursor-pointer select-none font-medium text-slate-600">
        {label}
      </summary>
      <div className="mt-2 space-y-1">{children}</div>
    </details>
  );
}
