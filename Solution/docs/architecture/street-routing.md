# Street routing and coordinated truck sectors

The live proposal and simulation use OSRM's **driving** profile over OpenStreetMap streets. Fixed journey times, assumed speeds and aerial-distance multipliers are not public planning options. The old C# and standalone contributor reference models are not the public route engine.

## Travel and optimization

`forecast_service/vendor/fillinq/roads.py` requests directional road distance/duration matrices with OSRM Table. Matrix blocks contain at most 100 unique coordinates. The routing objective is road meters; actual road seconds, service, intermediate unloading, final unloading and the yard return must fit each shift. Capacity uses conservatively rounded loads. Public optional-detour value defaults to zero, so a non-urgent site does not receive a reward for extra driving.

`territories.py` assigns contiguous angular service sectors around the common unloading site. Several rotations are compared using estimated working load and road compactness. Mandatory work receives the primary balancing weight. Each site's allowed truck stays fixed across that truck's loads. A truck can therefore make several unloading trips without being reassigned pickup stops on opposite sides of the city. Shared roads and the common yard/unloading legs can still overlap.

The route search tries increasing fleet sizes up to the configured availability. A later attempt cannot replace an earlier plan that served more mandatory stops. Remaining unserved locations retain a reason: missing coordinates, no nearby driving access, a stop larger than one load, an impossible shift, or sector/search limits. These warnings are not evidence that no feasible plan exists. The sector split and time-limited search are heuristics, not a global optimality or minimum-fleet proof.

## The map uses streets too

The worker requests an ordered OSRM Route for each used truck, including every pickup and unloading waypoint and the final return. Returned road legs are split into per-load paths. Those same legs provide the displayed road kilometers and driving time; the final geometry is checked against shift duration. The API includes `routing` provenance, truck `territory`, `roadPaths`, driving hours and snapped access coordinates.

The frontend renders `roadPaths` only. It does not turn stop coordinates into straight route lines if geometry is missing. Filtering by truck/load preserves the route order and street geometry. The collector manifest retains the same paths. Collection markers identify snapped road-access points, preserving the original site coordinate provenance. Sites requiring more than 1 km of snapping are reported as inaccessible; the yard and unloading site must also have connected nearby driving access.

## Provider and cache

- Default provider: `https://router.project-osrm.org`.
- Set `OSRM_BASE_URL` on the API process to an OSRM-compatible server, including a self-hosted service. The profile is `driving`.
- `ROAD_ROUTING_CACHE` overrides the disposable cache file. Default: `garbage-collector-roads-v1.sqlite` in the OS temporary directory. This is separate from the read-only source `sql.db`.
- Matrix pairs, access points and geometry responses are cached for seven days, keyed by provider and coordinates. Requests are serialized across worker processes and paced to at most one per second. Initial plans can take longer while the cache warms.
- No external road call occurs in unit tests. Provider behavior is exercised with explicit directional matrix and geometry fixtures.
- Network errors, unavailable paths and invalid geometry produce explicit errors. No constant-time, haversine or synthetic street-geometry fallback is used.

The public demo service is suitable for this local prototype, with no availability guarantee. Configure an appropriate provider or self-hosted OSRM for deployment. Routes retain OSRM/OpenStreetMap attribution.

## Interpretation and limits

OSRM's car profile is the requested street model. It does not establish access for a particular truck's height, mass, hazardous cargo or municipal permits. Table distances describe the provider's driving routes; optimizing stop order does not prove globally shortest possible road paths. Coordinates assigned to anonymous bins can still be synthetic: routing on actual streets does not verify that the bins exist there. Confirm site/depot/unloading positions before operational use.

CSV-only reading uploads remain valid forecasting inputs, but street routes require matching location coordinates. Missing positions stay unserved; the application does not reuse unrelated original inventory coordinates or silently revive a fixed-time mode.

## Verification

Regression tests cover directional/cached/batched road matrices, ordered street legs, zero-length colocated access, provider failures without aerial fallback, contiguous sector ownership across loads, inaccessible roads, actual driving-time limits and public removal of obsolete parameters. Browser checks cover real street shapes and summed road kilometers, capacity/shift bounds, truck/load inspection, mobile layout and accepted-manifest maps.

On 15 November 2026, the latest suites passed **389 tests: 210 API, 6 AppHost, 133 frontend and 40 Python**, with type checking and .NET/Nuxt builds passing. The existing Aspire CLI-bundle and Python dependency-deprecation warnings remain.

The live browser proposal used nine trucks and served 115 sites, reporting one missed mandatory stop under the short search budget. Its pickup sectors spanned approximately 9–95 degrees each around the unloading site, rather than assigning each truck stops around the entire city. An earlier live run served all mandatory sites with ten trucks; these time-limited results are not a global feasibility proof. A one-day live simulation also executed all three policies with street kilometers and an optimal bounded Gurobi sample check. These are execution checks, not operational fuel-savings claims.

Local artifacts: `/tmp/street-browser.log`, `/tmp/street-browser-proposal.json`, `/tmp/greencity-qa/street-route-{truck,fleet,mobile}.png`. Source SQLite remains unchanged. Time-limited route results can vary, and missed mandatory service must always remain visible.

References: [OSRM API](https://project-osrm.org/docs/v5.24.0/api/), [provider usage guidance](https://github.com/Project-OSRM/osrm-backend/wiki/Api-usage-policy).
