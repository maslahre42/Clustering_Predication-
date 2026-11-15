/** Small shared loading / empty / error state components (M11 requirement). */

interface PanelStateProps {
  label: string;
  hint?: string;
}

export function LoadingState({ label, hint }: PanelStateProps) {
  return (
    <div
      className="flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-4 text-sm text-slate-600"
      data-testid="loading-state"
    >
      <span className="inline-block h-3 w-3 animate-pulse rounded-full bg-slate-400" aria-hidden />
      <span>{label}…</span>
      {hint ? <span className="text-slate-400">{hint}</span> : null}
    </div>
  );
}

export function EmptyState({ label, hint }: PanelStateProps) {
  return (
    <div
      className="rounded-md border border-dashed border-slate-300 bg-white px-3 py-4 text-sm text-slate-500"
      data-testid="empty-state"
    >
      <p className="font-medium text-slate-600">{label}</p>
      {hint ? <p className="mt-1 text-slate-400">{hint}</p> : null}
    </div>
  );
}

export function ErrorState({ label, hint }: PanelStateProps) {
  return (
    <div
      className="rounded-md border border-red-300 bg-red-50 px-3 py-4 text-sm text-red-700"
      data-testid="error-state"
      role="alert"
    >
      <p className="font-semibold">{label}</p>
      {hint ? <p className="mt-1 break-words text-red-600">{hint}</p> : null}
    </div>
  );
}
