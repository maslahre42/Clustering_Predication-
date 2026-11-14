# UI theme and domain presentation

The current visual theme returns to the uploaded `idea of UI:UX` references, with larger typography, a fixed icon rail, white cards, softer borders, and a generous split map canvas. The earlier executive specification informs domain-state distinctions. CSS custom properties in `apps/web/app/assets/styles/tokens.css` provide one source for brand, neutral, material, historical-reading, and cutoff colors. Existing `--fleet-*` aliases and project-owned Vue controls consume them; Onyx theme overrides have been removed.

## Applied

- Green actions (`#087f48`), darker hover/active colors, subtle selections, readable slate text, and neutral surfaces/borders.
- Brown, green, and clear-glass material colors with coordinated soft surfaces and visible borders. Chart points and material badges share these colors.
- Separate historical reading bands: numeric values below 70%, values from 70% to below 100%, exactly 100%, explicit Overfull, and Unknown. Exactly 100% uses the elevated numeric color while retaining its numeric label; it is not Overfull.
- Red Overfull track and explicit label, without a numeric progress value. Unknown readings use a hatched track and explicit label. Zero remains a real recorded number.
- Blue historical-cutoff banner and lock icon.
- Custom calendar selection, hover, disabled, focus, and today styling; monospaced date-field values. An out-of-range today remains disabled.
- Shared surface tokens in existing panels, navigation, and selection treatments.
- Printable draft notes remain visible even while their editor is open. Printing records an actual UTC generation timestamp, waits for the UI to render it, then opens the print dialog. The printed page includes the cutoff, coordinate provenance, and a straight-line-preview limitation.

## Adaptations to the existing product

| Supplied concept | Implementation decision |
| --- | --- |
| Telemetry, sensors, or missing/deactivated sensors | The source is manual collection history. Unknown means no usable recorded percentage, not a diagnosed device condition. |
| Numeric bands imply urgency or priority | These colors describe past pre-emptying readings only. Selection remains explicit; there is no current-urgency inference. |
| Recently cleared state | Not inferred. A before-emptying observation cannot establish a current fill level after emptying. |
| ISO timestamps for source readings | Original observations retain their date-only ISO service days. No inspection times are invented. The print generation timestamp is a separate actual instant. |
| Calendar applies cutoff immediately or has its own Apply Selection footer | The calendar emits a draft date; the existing single calendar-footer Apply date action commits the cutoff and clears the draft plan. This avoids two competing commit controls. |
| Today quick shortcut | Today's marker does not override database date bounds. |
| Clear shows unconstrained history | Optional history fields can clear, but the global planning cutoff still applies. Planning date remains required. |
| Rename props and emit events from the design | Existing application contracts remain in use. `CollectionDatePicker.vue` is now a project-owned calendar; pure helpers own day/month navigation and inclusive bounds. |
| URL `?cutoff=` synchronization | Not introduced in this visual change. Existing request-local workspace state preserves the cutoff across modules; APIs continue to use `asOf`. |
| Slider maximum 95% | Retains 100%, allowing users to filter recorded full bins. |
| Three selected bins always means checked | Location selection is based on the bins matching active filters, including partially observed historical locations. |
| Separate container IDs and street names | Bin identity remains location UUID plus material. Source addresses and container IDs do not exist. |
| Estimated lift volume, fleet status, trends, dispatched/locked states | Not fabricated or added to the UI. They require additional data and workflow implementation. |
| Standard municipal dispatch CSV / TSP optimization | Existing CSV is an application export. Stop order uses nearest-neighbor or manual order, without a claim of optimality or a municipal standard. |
| Heilbronn directive compliance footer | Omitted because no supporting requirement or verification was supplied. The footer identifies a draft plan and its actual coordinate provenance. |

Recent header/sidebar text removals and the icon-only drawer toggle are preserved. Disabled controls retain native HTML semantics; CSS does not remove calendar cells from keyboard semantics using blanket `pointer-events: none`.

## Validation

Frontend regression tests cover reading-band boundaries, exactly full versus explicit Overfull, invalid/missing readings, and print timestamp/render ordering. Existing tests continue to cover date bounds, timezone-safe dates, selection, historical isolation, and exports. Run `pnpm --dir apps/web test`, `pnpm --dir apps/web typecheck`, and `pnpm --dir apps/web build`.

Visual calendar interactions and printed output still require a browser review; they have not been visually verified in this environment.
