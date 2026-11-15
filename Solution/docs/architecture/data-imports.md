# Data & imports

CSV selection lives in **Data & imports** (the database icon in the sidebar), replacing the old status-only page. CSV management and the active-source summary are available only on Data & imports; the Plan your next collection page contains collection settings and results.

The data page accepts one `.csv` file, case insensitive, up to 2 MB through a native file-picker button or drag and drop. Nested drag-enter/leave events preserve the drop highlight. Multiple files, unsupported extensions, unreadable files and empty files are rejected before activation.

`createProposalDataset` reads the file and calls `POST /api/dataset-validation?asOf=...`. The endpoint invokes worker action `dataset`, which uses the existing strict CSV validator and returns accepted record/location/site-type counts, file-wide date coverage, material counts, warnings and a content fingerprint. It does not fit a forecast, route trucks or write the database. Header-only files and invalid records produce structured row-level errors. The page adds the header offset to the validator's data-record numbers so its displayed CSV row numbers include the header.

Only a successful validation activates the selected file and metadata. Rejected uploads leave the previous active source intact. A newer selection aborts older validation; stale reads and responses cannot activate an old file. Leaving the page cancels pending work while preserving the last completed selection. Restoring the collection database clears the file and metadata.

The selection and metadata use request/session-local Nuxt state. CSV data applies to forecasts, scenario comparisons, optimization and simulation; inventory and historical analytics retain the connected database. Analysis requests still apply the inclusive planning cutoff. File-wide summary counts/date coverage do not imply future observations enter a model.

Uploaded readings do not provide coordinates through the current CSV path. Road routing still requires a matching coordinate source and never substitutes invented or original-inventory positions for unmatched uploaded sites.

Workspace state owns draft invalidation when the analysis dataset changes, so importing from the Data page also clears an existing collection draft. The original inventory and recorded history remain unchanged. Completed optimization results independently invalidate when their dataset context changes.

The redesign includes an upload panel, active-dataset summary, validation feedback, an optional schema example, a forecasting shortcut and compact connection cards. SQLite health is measured; OSRM/map availability is described as checked during route calculation rather than incorrectly reported as disconnected or globally healthy.

Ownership: `features/system/components/SystemStatus.vue`, `features/system/styles.css`, `features/proposal/state/createProposalDataset.ts`, `features/workspace/model.ts`, dataset API contracts, `Features/Dataset/DatasetEndpoints.cs` and `worker.dataset_validation`.

Regression coverage includes file-picker/drop event binding, validation-before-activation, invalid rows preserving the source, multiple/oversize/wrong-type rejection, cancellation/races, nested drag state, metadata persistence/restoration, global draft invalidation, source isolation, endpoint binding/errors and relocated worker execution.
