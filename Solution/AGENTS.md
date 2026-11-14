# Working in Garbage Collector

Start with [CODE_INDEX.md](CODE_INDEX.md). Use its task map to open only relevant source and tests. Read longer architecture/design documents only when the task needs them.

- Use pnpm for the Nuxt frontend; .NET 10 for the API and Aspire.
- Preserve the current UI during refactors unless a design change was requested.
- Keep feature logic in feature `state`/`domain` modules; Vue components render props/state and emit events. Shared UI must not import feature implementations or workspace state.
- Every new or changed logic requires unit/regression tests. Include interaction/request-binding coverage when changing sorting, filtering, or API parameters.
- SQLite source data is read-only. Do not migrate, seed, or edit `sql.db` for application changes.
- Planning cutoff is inclusive. Never read subsequent observations into historical results. Changing the date clears draft routes, selections, inspection, and notes.
- Fill readings are pre-emptying observations. Numeric, overfull, and unknown are distinct; never invent a percentage. Bin identity is location plus material.
- Keep modules request-local; no global mutable workspace state. Preserve coordinate provenance and the straight-line route disclaimer.
- Avoid generated/build outputs, lockfiles, raw data, notebooks, and `idea of UI:UX/` in broad searches unless relevant. Use targeted `rg` searches.
- Run relevant tests, then required type/build checks. Report browser verification separately. API code changes require restarting Aspire/API when using `dotnet run`.
- Update the relevant `CODE_INDEX.md` row if file ownership or architecture changes. Keep this entrypoint brief; detailed explanations belong in `docs/`.
