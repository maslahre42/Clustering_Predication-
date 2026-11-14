# Review of commit 19b9a0f — started to merge

> Follow-up implementation: the manifest/date handoff and mandatory-risk priority were corrected, every operating parameter/calendar day is exposed, generated environments were removed from tracking without deleting local files, and the app now uses Omar's actual Python forecast/router/simulation. See [integration verification](../Solution/docs/forecast-integration-verification.md). The findings below preserve the reviewed commit's original behavior.

Reviewed the pinned commit `19b9a0f5540b800665849066d0a8a09d89627f67`, whose Git author is Omar Mohab. The user identifies this as Claude's work; Git itself does not establish which assistant authored it. Its parent is `dec7e27`. The separate `57ddf36` OSRM/notebook commit exists on another history branch and is **not** the commit reviewed here.

## Findings, in priority order

### 1. P1 — proposal handoff changes the collection date and loses forecast context

Source: [CollectionProposalView.vue, useAsPlan](../Solution/apps/web/app/features/proposal/components/CollectionProposalView.vue:26), [applyProposal](../Solution/apps/web/app/features/manifest/state/createCollectionPlan.ts:47).

The proposal is explicitly for the next working day after `asOf`, but handoff passes only bin keys and flattened stop order. The existing manifest continues using `asOf` as its collection date and existing historical bin values. It does not retain `proposal.planDate`, forecast values, settings or truck/load assignments.

Reproduced with the commit's own sample proposal and the actual reactive workspace/export functions:

```text
Direct proposal CSV:
plan date 2026-08-17; truck 1; load 1; B:white; expected fill 90.0%

After "Use as collection plan", manifest CSV:
planning date 2026-08-14; B:white; historical pre-emptying fill 50%
```

The original sample has two loads; the target plan model has no truck/load representation. Multiple truck routes become a single flattened depot round trip in the manual manifest. Loss of truck splits is acknowledged in the architecture document, but changing the actual plan date is an additional concrete error.

**Recommendation:** keep historical cutoff and intended collection date separate. Preserve proposal metadata and truck/load boundaries in an accepted plan, or make the handoff explicitly a conversion to manual selection and retain the correct collection date. Do not fix this by changing `asOf` alone: that refetches history and clears workspace state. Add an integration test from proposal acceptance through manifest display and CSV/print output. The direct proposal CSV is the currently safer export because it retains plan date, forecasts, truck and load.

### 2. P1 — mandatory stop scheduling can skip the most urgent feasible stop

Source: [mandatory scheduling](../Solution/apps/api/Features/Proposal/RoutePlanner.cs:58), [candidate choice](../Solution/apps/api/Features/Proposal/RoutePlanner.cs:123).

Mandatory stops are sorted by risk, but `TakeNearest(mandatory)` then chooses minimum driving **plus service** cost without enabling its risk-order mode. Even under fixed travel times, a less urgent site with fewer bins can jump ahead of a higher-risk site. When trucks/shifts are limited, the higher-risk site is left unserved.

Reproduced against the actual C# implementation in a temporary console referencing the API project:

```text
Settings: 1 truck, 1-hour shift, default 10-minute drives and 5-minute/bin service.
HIGH: mandatory, 99% risk, 3 bins.
LOW: mandatory, 71% risk, 1 bin.

HIGH alone: served, exactly 1 hour.
Both supplied: LOW served; HIGH unserved with fleet_limit.
```

This contradicts the documented “most urgent first” behavior and matters precisely when the operator needs prioritization during limited capacity.

**Recommendation:** define priority explicitly: preserve risk priority for mandatory service, or use an objective that penalizes missing high-risk mandatory sites more strongly. Nearest/service cost can break ties within an appropriate urgency band. Add the constrained two-site case above; current mandatory-route tests do not cover unequal risks and unequal service times together.

### 3. P1 — a complete local Python environment was added to Git

Source: [tracked environment configuration](../fillinq-router/.venv/pyvenv.cfg:1). The root ignore file does not exclude `.venv/` or Python bytecode.

The commit adds **12,459 files totaling approximately 515.3 MiB of uncompressed tracked content** under `fillinq-router/.venv/`, including installed packages and platform-specific libraries. It also adds Python bytecode under `Omar-Work/`. The environment configuration points at a local macOS Python 3.9 installation; it is not a portable installation of the project.

This overwhelms the actual 39-file application change and burdens checkout, indexing and code review. The newly added combined review calls this environment untracked, which no longer matches this commit.

**Recommendation:** remove generated environments/bytecode from tracking while retaining them locally if needed, and add ignore rules. Reproduce environments from dependency manifests. If this commit has already been shared, do not rewrite shared history without coordinating with the team.

### 4. P2 — the settings interface claims every number is editable but omits seven numeric settings

Source: [setting groups](../Solution/apps/web/app/features/proposal/domain/settings.ts:24), [form claim and iteration](../Solution/apps/web/app/features/proposal/components/ProposalSettingsForm.vue:27).

The form renders only `SETTING_GROUPS`, which omits `avgSpeedKph`, `detourFactor`, the four yard/disposal coordinate values, and `neighbourProbability`. These exist in defaults, API overrides and request construction, but have no user controls. Validation also iterates only the displayed field list.

The concrete user impact is switching fixed travel to zero: the planner uses assumed speed, detour and placeholder yard/disposal locations that the operator cannot change in the advertised operating-settings form.

**Recommendation:** expose these settings, possibly under an advanced section with assumption labels, and validate every numeric setting. Alternatively accurately limit the UI claim and remove an unsupported coordinate-mode workflow. Add a test comparing editable/validated settings against the complete contract.

## What the commit actually adds

The application now has a connected C# proposal pipeline behind `GET /api/proposal`, replacing the former forecast placeholder in the Nuxt sidebar:

1. Inclusive historical cutoff, with proposal dated on the next working day.
2. Filling cycles derived from pre-emptying visits, not differences between visit readings.
3. A partially pooled log-normal rate model with censored full/overfull observations, fitted by an EM-style procedure.
4. Due, neighboring, optional, skipped and no-forecast bin decisions, aggregated by physical site.
5. A constructive multi-load routing heuristic enforcing load and shift constraints, final unloading and return.
6. Per-truck/load tables, risk inspection, settings and a direct route-sheet CSV.

This is a native rewrite inspired by the prototypes, not direct integration of Omar's Python model, OR-Tools or Zakaria's Gurobi solver. It has no fitted seasonal/vacation effect and does not provide an optimality guarantee. The architecture document discloses these limits and summer probability overestimation.

Useful choices include cutoff-safe training, preserved overflow categories, explicit unserved reasons, rejecting oversized sites rather than clipping them, separating loads from trucks, and honestly omitting kilometers when travel uses fixed minutes. The documentation's correction of the older Zakaria default settings is also valid; earlier comparison tables had become stale after that project's correction.

The commit does not add dataset upload to the Nuxt application or a proposal map. The four-project challenge workflow is therefore not yet fully merged, even though forecast-to-route behavior is now connected.

## Verification performed

- Inspected the new backend modules, frontend state/domain/view integration, tests and architecture claims.
- Frontend suite: **104 passed, zero failed/skipped**.
- Nuxt TypeScript check: **passed**.
- Backend/test-runner build: **passed**, with the existing Aspire CLI-bundle warning.
- Actual C# urgency counterexample: **reproduced**.
- Actual reactive workspace/CSV date counterexample: **reproduced**.
- The complete in-process backend xUnit runner produced no result in this environment and was stopped. A full backend test pass is **not** claimed.
- No browser interaction test, live API request, forecast calibration benchmark or deployment was performed.

Review probes were created in `/tmp/claude-last-commit-review`. No application source or source database was changed by this review. This document is the only newly authored repository file.
