"""Hosted deployment knobs — environment-driven, read ONLY in ``src/api``.

The single-process Docker deployment (README "Deploy") targets free hosting
tiers (about 0.1 CPU / 512 MB). Two optional environment variables bound the
solver workload for those environments:

- ``WASTECITY_SOLVER_TIME_LIMIT_S``: positive float; overrides the §4.6
  ``RoutingConfig.solver_time_limit_s`` *default* for requests that did not
  explicitly override it. An explicit ``routing_config.solver_time_limit_s``
  in the request body always wins.
- ``WASTECITY_MAX_STOPS``: positive int; caps how many policy-selected
  candidates are handed to the OR-Tools solver, deterministically (the first
  N in the §3.3 selection order: predicted_fill desc, ties by location and
  material). The remainder surfaces in the route response's
  ``solution.unserved`` with an explicit ``hosted_demo_stop_cap`` reason —
  never silently dropped (AGENTS rule 9).

These are deployment knobs of this prototype, NOT new assumptions about the
challenge: responses label them "[deployment setting]" and say so. Unset →
behaviour is byte-identical to the local default.

Invalid values never crash the service (500-free per the deployment brief):
a warning is logged and the variable is ignored, i.e. it falls back to the
unset behaviour. Chosen alternative to a startup error so a bad platform
config cannot take the whole demo down.
"""

from __future__ import annotations

import logging
import math
import os

logger = logging.getLogger(__name__)

ENV_SOLVER_TIME_LIMIT_S = "WASTECITY_SOLVER_TIME_LIMIT_S"
ENV_MAX_STOPS = "WASTECITY_MAX_STOPS"


def hosted_solver_time_limit_s() -> float | None:
    """Effective solver time-limit override, or ``None`` when unset/invalid.

    Valid: a finite float > 0. Invalid (unparseable, non-finite or
    non-positive) → warning log, ``None`` (falls back to the §4.6 default;
    500-free fallback choice).
    """
    raw = os.environ.get(ENV_SOLVER_TIME_LIMIT_S)
    if raw is None or raw.strip() == "":
        return None
    try:
        value = float(raw)
    except ValueError:
        logger.warning(
            "%s=%r is not a float — ignored, using the §4.6 default "
            "solver_time_limit_s (deployment knob, not a crash)",
            ENV_SOLVER_TIME_LIMIT_S,
            raw,
        )
        return None
    if not math.isfinite(value):
        # inf/nan/1e400 pass naive > 0 checks but would poison the solver's
        # wall-clock cap (and 500 a request) — rejected like any invalid value.
        logger.warning(
            "%s=%r must be a finite positive float — ignored, using the "
            "§4.6 default solver_time_limit_s (deployment knob, not a crash)",
            ENV_SOLVER_TIME_LIMIT_S,
            raw,
        )
        return None
    if value <= 0:
        logger.warning(
            "%s=%r must be a positive float — ignored, using the §4.6 "
            "default solver_time_limit_s (deployment knob, not a crash)",
            ENV_SOLVER_TIME_LIMIT_S,
            raw,
        )
        return None
    return value


def hosted_max_stops() -> int | None:
    """Effective solver stop cap, or ``None`` when unset/invalid.

    Valid: an int > 0. Invalid (unparseable or non-positive) → warning log,
    ``None`` (no cap; 500-free fallback choice).
    """
    raw = os.environ.get(ENV_MAX_STOPS)
    if raw is None or raw.strip() == "":
        return None
    try:
        value = int(raw)
    except ValueError:
        logger.warning(
            "%s=%r is not an int — ignored, no solver stop cap (deployment knob, not a crash)",
            ENV_MAX_STOPS,
            raw,
        )
        return None
    if value <= 0:
        logger.warning(
            "%s=%r must be a positive int — ignored, no solver stop cap "
            "(deployment knob, not a crash)",
            ENV_MAX_STOPS,
            raw,
        )
        return None
    return value


__all__ = [
    "ENV_MAX_STOPS",
    "ENV_SOLVER_TIME_LIMIT_S",
    "hosted_max_stops",
    "hosted_solver_time_limit_s",
]
