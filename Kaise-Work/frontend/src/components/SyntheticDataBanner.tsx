/**
 * "Synthetic demo data" banner (M11 req. 7). Rendered whenever demo geography
 * or demo values are in play — i.e. assumptions were returned by /route or the
 * distance provenance is straight-line derived (§5.3: the frontend must render
 * these labels). Never presented as observed fact.
 */
export function SyntheticDataBanner({ assumptions }: { assumptions: string[] }) {
  return (
    <div
      className="rounded-md border border-amber-400 bg-amber-50 px-4 py-3 text-sm text-amber-900"
      data-testid="synthetic-banner"
      role="note"
    >
      <p className="font-semibold">
        Synthetic demo data in play — coordinates, fleet, densities and thresholds are
        labelled [demo assumption], not observed facts.
      </p>
      {assumptions.length > 0 ? (
        <ul className="mt-2 list-disc pl-5">
          {assumptions.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
