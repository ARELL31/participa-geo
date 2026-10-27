"""Scenario persistence service and in-memory creation limiter (T6).

The service validates the whole closed request before writing, computes the
comparison in memory and then inserts the header plus the 125 results in one
transaction. A failure rolls the transaction back, so no partial scenario exists.

The limiter is intentionally process-local: it enforces 10 creations/minute and
one active request per client for this single-worker MVP. It is not a distributed
rate limit and would need a shared store before scaling the API horizontally.
"""

from __future__ import annotations

import hashlib
import json
import math
import threading
import time
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from participa_geo.api.schemas.scenarios import ScenarioComparison, ScenarioDTO, ScenarioRequest
from participa_geo.db import models
from participa_geo.db.repository import Repository
from participa_geo.scenarios.rules import (
    ScenarioConflictError,
    ScenarioInputError,
    simulate_scenario,
)


class ScenarioRateLimitError(RuntimeError):
    """Raised when a client exceeds the creation budget or already has a request."""

    def __init__(self, retry_after_seconds: int = 1, *, active: bool = False):
        super().__init__("Límite de creación de escenarios excedido.")
        self.retry_after_seconds = max(1, int(retry_after_seconds))
        self.active = active


class ScenarioRateLimiter:
    """Process-local sliding-window limiter (single-worker MVP only)."""

    def __init__(self, *, limit: int = 10, window_seconds: float = 60.0) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = {}
        self._active: set[str] = set()
        self._lock = threading.Lock()

    @contextmanager
    def acquire(self, client_key: str) -> Iterator[None]:
        now = time.monotonic()
        with self._lock:
            if client_key in self._active:
                raise ScenarioRateLimitError(active=True)
            events = self._events.setdefault(client_key, deque())
            cutoff = now - self.window_seconds
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                retry_after = math.ceil(events[0] + self.window_seconds - now)
                raise ScenarioRateLimitError(retry_after_seconds=retry_after)
            events.append(now)
            self._active.add(client_key)
        try:
            yield
        finally:
            with self._lock:
                self._active.discard(client_key)


def _model_sha256(model: models.ModelRecord) -> str:
    """Return the model artifact's logical hash, or a canonical fallback digest."""
    hashes = model.hashes or {}
    logical = hashes.get("logical_hash")
    if isinstance(logical, str) and len(logical) == 64:
        return logical
    canonical = json.dumps(
        hashes, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _model_error(model_run_id: UUID) -> ScenarioInputError:
    return ScenarioInputError(
        [
            {
                "loc": ["body", "model_run_id"],
                "msg": "model_run_id debe identificar el modelo publicado.",
                "type": "value_error",
                "reason": "model_not_published",
                "model_run_id": str(model_run_id),
            }
        ]
    )


def _to_result_records(
    scenario_id: UUID, comparison: ScenarioComparison
) -> list[models.ScenarioResultRecord]:
    return [
        models.ScenarioResultRecord(
            scenario_id=scenario_id,
            territory_id=result.territory_id,
            municipality_code=result.municipality_code,
            municipality_name=result.municipality_name,
            baseline_abstention_pct=result.baseline_abstention_pct,
            hypothetical_abstention_pct=result.hypothetical_abstention_pct,
            baseline_error_lower_pct=result.baseline_error_lower_pct,
            baseline_error_upper_pct=result.baseline_error_upper_pct,
            hypothetical_error_lower_pct=result.hypothetical_error_lower_pct,
            hypothetical_error_upper_pct=result.hypothetical_error_upper_pct,
            requested_reduction_pp=result.requested_reduction_pp,
            effective_reduction_pp=result.effective_reduction_pp,
            risk_a=result.risk_a,
            risk_b=result.risk_b,
            risk_a_unstable=result.risk_a_unstable,
            risk_b_unstable=result.risk_b_unstable,
            selected=result.selected,
        )
        for result in comparison.results
    ]


class ScenarioService:
    """Create and read persisted scenarios over a caller-provided session."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = Repository(session)

    def create(self, request: ScenarioRequest) -> ScenarioDTO:
        published = self.repository.get_published_model_run_id()
        if published is None:
            raise ScenarioConflictError(
                "No se ha cargado ningún modelo publicado; no es posible crear escenarios."
            )
        if request.model_run_id != published:
            raise _model_error(request.model_run_id)

        model = self.repository.get_model(published)
        if model is None:
            raise ScenarioConflictError(
                "No se ha cargado el modelo publicado; no es posible crear escenarios."
            )

        predictions, total = self.repository.get_predictions(
            model_run_id=published,
            target_year=request.target_year,
            territory_id=None,
            page=1,
            page_size=125,
        )
        if total != 125 or len(predictions) != 125:
            raise ScenarioConflictError(
                "El universo publicado no contiene las 125 predicciones requeridas."
            )

        comparison = simulate_scenario(predictions, request)

        scenario_id = uuid4()
        created_at = datetime.now(UTC)
        scenario = models.ScenarioRecord(
            scenario_id=scenario_id,
            model_run_id=comparison.model_run_id,
            target_year=comparison.target_year,
            requested_reduction_pp=comparison.requested_reduction_pp,
            assumption_code=comparison.assumption_code,
            assumption_version=comparison.assumption_version,
            rationale_text=comparison.rationale_text,
            rules_version=comparison.rules_version,
            input_sha256=comparison.input_sha256,
            model_sha256=_model_sha256(model),
            selection=[str(territory_id) for territory_id in comparison.selected_territory_ids],
            created_at=created_at,
        )
        results = _to_result_records(scenario_id, comparison)

        try:
            self.repository.insert_scenario(scenario)
            self.repository.insert_scenario_results(scenario_id, results)
            self.session.commit()
        except BaseException:
            self.session.rollback()
            raise

        return ScenarioDTO(
            scenario_id=scenario_id,
            model_sha256=scenario.model_sha256,
            created_at=created_at,
            **comparison.model_dump(),
        )

    def get(self, scenario_id: UUID) -> ScenarioDTO | None:
        stored = self.repository.get_scenario(scenario_id)
        if stored is None:
            return None
        scenario, results = stored
        return ScenarioDTO(
            scenario_id=scenario.scenario_id,
            model_run_id=scenario.model_run_id,
            target_year=scenario.target_year,
            requested_reduction_pp=scenario.requested_reduction_pp,
            assumption_code=scenario.assumption_code,
            assumption_version=scenario.assumption_version,
            rationale_text=scenario.rationale_text,
            rules_version=scenario.rules_version,
            input_sha256=scenario.input_sha256,
            model_sha256=scenario.model_sha256,
            selected_territory_ids=[UUID(value) for value in scenario.selection],
            created_at=scenario.created_at,
            results=[
                {
                    "territory_id": result.territory_id,
                    "municipality_code": result.municipality_code,
                    "municipality_name": result.municipality_name,
                    "baseline_abstention_pct": result.baseline_abstention_pct,
                    "hypothetical_abstention_pct": result.hypothetical_abstention_pct,
                    "baseline_error_lower_pct": result.baseline_error_lower_pct,
                    "baseline_error_upper_pct": result.baseline_error_upper_pct,
                    "hypothetical_error_lower_pct": result.hypothetical_error_lower_pct,
                    "hypothetical_error_upper_pct": result.hypothetical_error_upper_pct,
                    "requested_reduction_pp": result.requested_reduction_pp,
                    "effective_reduction_pp": result.effective_reduction_pp,
                    "risk_a": result.risk_a,
                    "risk_b": result.risk_b,
                    "risk_a_unstable": result.risk_a_unstable,
                    "risk_b_unstable": result.risk_b_unstable,
                    "selected": result.selected,
                }
                for result in results
            ],
        )


__all__ = [
    "ScenarioRateLimitError",
    "ScenarioRateLimiter",
    "ScenarioService",
]
