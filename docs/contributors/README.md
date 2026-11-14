# Contributor work and business-logic analysis

Reviewed on 14 November 2026 from the working tree and all locally available Git history. These reports describe the implementations as found; they do not change application code or source data.

For shared capabilities, the preferred implementation at each layer, challenge coverage and a proposed team/integration plan, read the [project comparison and combination recommendation](../project-comparison-and-combination.md).

## Reports

| Person / recorded identity | Work area | Detailed report | Attribution basis |
| --- | --- | --- | --- |
| Monir Nououali | Historical collection workspace, ASP.NET API, Nuxt UI, deployment | [Monir](monir-nououali.md) | `c8128d7` imports `Solution/`; additional housekeeping commits |
| Omar Mohab / `omarmohab2001` | Probabilistic forecasts, risk selection, multi-trip routing, simulation, Streamlit | [Omar](omar-mohab.md) | `b27bb42` adds the original `fillinq-router/`; current counterpart is `Omar-Work/` |
| Zakarea Alsharef / Zakaria | Exploratory notebook, clustering, demand prediction, Gurobi routing | [Zakaria](zakaria-alsharef.md) | `13d53f3` adds original `main.ipynb`; expanded work is under `Zakaria-Work/` |
| Kaise | Strict data processing, descriptive analysis, baseline forecasts, FastAPI/React route-planning prototype | [Kaise](kaise.md) | Folder attribution only: `Kaise-Work/` is currently untracked |
| `a-meine` | Initial repository creation | [a-meine](a-meine.md) | `1de7c47` adds the root README |

Omar's two author names use the same email and are treated as one person. Zakaria's folder spelling differs from the Git author spelling; the report makes that distinction explicit. No full name is inferred for Kaise or `a-meine`.

## Scope and evidence limits

The analysis covers the four application/pipeline trees, Python modules, notebook source cells, API/domain/state modules, existing tests, saved metrics, deployment files, and supporting project documentation. Notebook outputs and saved evaluation numbers are historical artifacts, not new executions. The challenge DOCX/PPTX/PDF material is supplied context, not automatically a person's authored deliverable.

The working tree already contains staged changes, deleted original paths, and three untracked work folders. Those changes were preserved. The current folder content can extend beyond what its owner's commits establish; an import commit establishes that a person contributed the imported implementation, not that they personally wrote every line or that later local work belongs to them.

The main comparison is:

| Business question | Monir | Omar | Zakaria | Kaise |
| --- | --- | --- | --- | --- |
| What does a reading mean? | Historical pre-emptying observation | Pre-emptying observation followed by reset | Uses differences between readings to infer emptying/growth | Keeps semantics unresolved; reports descriptive changes |
| What is `overfull`? | Separate category; numeric value absent | At least 100%, censored in fitting | Artificial 110% numerical value plus flag | Separate category; numeric value absent |
| Forecast | Integration placeholder | Partially pooled log-normal cycle-rate model | Linear extrapolation with holiday multiplier | Persistence or median numeric-change rate |
| Collection choice | User selection / recorded collections on selected day | Overflow probability, mandatory/optional sites, neighboring bins | Urgency bands; demo routes first 24 urgent rows | Threshold + configurable buffer; optional overfull override |
| Routing | Nearest-neighbor straight-line preview | OR-Tools, volume/weight/time dimensions, reload copies | Gurobi MILP, volume/weight/shift, one final unload | OR-Tools volume/weight, disposal nodes, shift adjustment afterward |
| Fleet output | Unavailable | Heuristic fleet escalation and fixed truck cost | Vehicle-use variables with dispatch penalty | Aggregate capacity-based requirement, separate from actual fleet used |
| Interface | Nuxt/Vue + ASP.NET + SQLite | Streamlit | Jupyter + Folium HTML | React + FastAPI |

These implementations are separate systems. There is no shared deployed forecasting/routing service connecting all four. Their default capacities, density assumptions, time budgets, coordinate generation and evaluation protocols differ. Their metrics must not be combined into one claimed performance result.

## Supporting work whose authorship is not established

- [PreZero research report](../../PreZero_Germany_report.pdf): a 12-page operational specification/handoff covering assets, lifting compatibility, color chambers, mass versus volume, uncertainty, evaluation and data requests. It distinguishes local equipment, manufacturer examples and assumptions. It proposes capabilities rather than implementing an optimizer. The staged file and local metadata do not establish a contributor identity, so it is not credited to a person here. External factual claims were not independently revalidated in this code review.
- [Readiness review](../../Solution/docs/challenge-readiness-review.md): existing cross-project assessment with useful correctness findings. Its links reference the old notebook/router paths and some simulation figures predate the currently saved Omar results. Each report below uses current code and artifacts for its conclusions.
- [Location proposal and application record](../../Solution/docs/heilbronn-location-sql-proposal.md): documents a local coordinate update with backup/audit, including 109 official-map points and 340 regional points. Coordinates can describe mapped sites while their assignment to anonymized UUIDs remains synthetic. This is associated with Monir's work area, with local-change attribution qualified in his report.

## Verification of these reports

Source references and report links were checked locally. The reports distinguish source-code inspection, existing test coverage and saved execution evidence. Application test suites, model training, backtests, Gurobi runs, deployments and browser sessions were not rerun for this documentation task. The default Python environment lacks the scientific/test packages needed for the Python prototypes.
