import type { ForecastMethod } from "../lib/api";

/**
 * Shared forecast parameters (§5.2 ForecastRequest): as_of_date (ISO, from the
 * dataset's last observed date), horizon_days ≥ 1, method. Horizon default 28 d
 * = observed median reading gap (docs/contracts.md §2.1) — labelled, not magic.
 * (ForecastRequest itself allows omitting horizon_days for the server default.)
 */
export interface ForecastParams {
  as_of_date: string;
  horizon_days: number;
  method: ForecastMethod;
}

export const DEFAULT_HORIZON_DAYS = 28; // [observed] median gap 28 d (§2.1) — demo default

export function ForecastParamsForm({
  value,
  onChange,
  disabled,
}: {
  value: ForecastParams;
  onChange: (next: ForecastParams) => void;
  disabled?: boolean;
}) {
  const inputClass =
    "rounded border border-slate-300 bg-white px-2 py-1 text-sm disabled:opacity-50";

  return (
    <div className="flex flex-wrap items-end gap-3" data-testid="forecast-params">
      <label className="flex flex-col text-xs font-medium text-slate-600">
        As-of date (ISO)
        <input
          type="date"
          value={value.as_of_date}
          disabled={disabled}
          onChange={(e) => onChange({ ...value, as_of_date: e.target.value })}
          className={`mt-1 ${inputClass}`}
          data-testid="as-of-input"
        />
      </label>
      <label className="flex flex-col text-xs font-medium text-slate-600">
        Horizon (days)
        <input
          type="number"
          min={1}
          step={1}
          value={Number.isNaN(value.horizon_days) ? "" : value.horizon_days}
          disabled={disabled}
          onChange={(e) => {
            const parsed = Number.parseInt(e.target.value, 10);
            onChange({ ...value, horizon_days: Number.isNaN(parsed) ? Number.NaN : parsed });
          }}
          className={`mt-1 ${inputClass} w-24`}
          data-testid="horizon-input"
        />
        <span className="mt-0.5 text-[10px] font-normal text-slate-400">
          default 28 d = observed median reading gap
        </span>
      </label>
      <label className="flex flex-col text-xs font-medium text-slate-600">
        Method
        <select
          value={value.method}
          disabled={disabled}
          onChange={(e) => onChange({ ...value, method: e.target.value as ForecastMethod })}
          className={`mt-1 ${inputClass}`}
          data-testid="method-select"
        >
          <option value="persistence">persistence</option>
          <option value="rate">rate</option>
        </select>
      </label>
    </div>
  );
}
