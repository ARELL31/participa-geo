from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

import participa_geo.scenarios.service as service_module
from participa_geo.api.schemas.scenarios import ScenarioRequest
from participa_geo.db.models import ModelRecord, PredictionRecord
from participa_geo.scenarios.rules import ScenarioInputError
from participa_geo.scenarios.service import ScenarioService
from participa_geo.territory import DistrictPlan, TerritoryLevel

MODEL_ID = UUID("00000000-0000-0000-0000-0000000000aa")


class FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class FakeRepository:
    def __init__(
        self,
        *,
        level: TerritoryLevel = "municipality",
        district_plan: DistrictPlan | None = None,
        mixed_scope: tuple[TerritoryLevel, DistrictPlan | None] | None = None,
    ) -> None:
        self.level = level
        self.district_plan = district_plan
        self.mixed_scope = mixed_scope
        self.persisted = False
        self.predictions = self._predictions()

    def _predictions(self) -> list[PredictionRecord]:
        records = []
        for index in range(125):
            level, plan = self.level, self.district_plan
            if index == 1 and self.mixed_scope is not None:
                level, plan = self.mixed_scope
            territory_id = uuid4()
            code = f"{index + 1:03}" if level == "municipality" else f"{index + 1:02}"
            records.append(
                PredictionRecord(
                    territory_id=territory_id,
                    municipality_code=code if level == "municipality" else None,
                    municipality_name=f"Territory {code}",
                    target_year=2027,
                    estimated_abstention_pct=45.0,
                    historical_error_lower_pct=43.0,
                    historical_error_upper_pct=47.0,
                    risk="medium",
                    risk_unstable=False,
                    eligible=True,
                    quality=None,
                    model_run_id=MODEL_ID,
                    level=level,
                    territory_code=code,
                    district_plan=plan,
                    state_code="14",
                )
            )
        return records

    def get_published_model_run_id(self):
        return MODEL_ID

    def get_model(self, model_run_id):
        return ModelRecord(
            model_run_id=MODEL_ID,
            family="M0",
            parameters={},
            features=[],
            cut_dates={},
            hashes={},
            dependencies={},
            metrics={},
            exclusions={},
            created_at=datetime.now(UTC),
            level=self.level,
            district_plan=self.district_plan,
        )

    def get_predictions(self, **kwargs):
        return self.predictions, len(self.predictions)

    def insert_scenario(self, scenario):
        self.persisted = True

    def insert_scenario_results(self, scenario_id, results):
        self.persisted = True


def _request(territory_ids: list[UUID], *, level: TerritoryLevel | None = None) -> ScenarioRequest:
    return ScenarioRequest(
        model_run_id=MODEL_ID,
        target_year=2027,
        territory_ids=territory_ids,
        reduction_pp=1,
        assumption_code="preventive_exploration",
        level=level,
    )


def _exercise_service(monkeypatch, repository: FakeRepository, request: ScenarioRequest):
    monkeypatch.setattr(service_module, "Repository", lambda session: repository)
    session = FakeSession()
    result = ScenarioService(session).create(request)
    return result, session


def test_scenario_service_accepts_explicit_matching_level(monkeypatch):
    repository = FakeRepository(level="municipality")
    result, session = _exercise_service(
        monkeypatch,
        repository,
        _request([repository.predictions[0].territory_id], level="municipality"),
    )

    assert result.model_run_id == MODEL_ID
    assert result.level == "municipality"
    assert result.district_plan is None
    assert session.committed
    assert repository.persisted


def test_scenario_service_accepts_matching_district_level_and_plan(monkeypatch):
    repository = FakeRepository(level="federal_district", district_plan="DERFE2023")
    result, session = _exercise_service(
        monkeypatch,
        repository,
        _request([repository.predictions[0].territory_id], level="federal_district"),
    )

    assert result.level == "federal_district"
    assert result.district_plan == "DERFE2023"
    assert session.committed


def test_scenario_service_rejects_explicit_level_mismatch_before_persisting(monkeypatch):
    repository = FakeRepository(level="municipality")
    request = _request([repository.predictions[0].territory_id], level="federal_district")
    monkeypatch.setattr(service_module, "Repository", lambda session: repository)
    session = FakeSession()

    with pytest.raises(ScenarioInputError, match="validación") as error:
        ScenarioService(session).create(request)

    assert error.value.errors[0]["reason"] == "scenario_level_mismatch"
    assert not repository.persisted
    assert not session.committed


def test_scenario_service_rejects_mixed_territory_levels(monkeypatch):
    repository = FakeRepository(level="municipality", mixed_scope=("federal_district", "DERFE2023"))
    request = _request(
        [repository.predictions[0].territory_id, repository.predictions[1].territory_id]
    )
    monkeypatch.setattr(service_module, "Repository", lambda session: repository)

    with pytest.raises(ScenarioInputError) as error:
        ScenarioService(FakeSession()).create(request)

    assert any(item["reason"] == "mixed_territory_scope" for item in error.value.errors)
    assert not repository.persisted


def test_scenario_service_rejects_mixed_district_plans(monkeypatch):
    repository = FakeRepository(
        level="federal_district",
        district_plan="DERFE2023",
        mixed_scope=("federal_district", "DERFE2021"),
    )
    request = _request(
        [repository.predictions[0].territory_id, repository.predictions[1].territory_id],
        level="federal_district",
    )
    monkeypatch.setattr(service_module, "Repository", lambda session: repository)

    with pytest.raises(ScenarioInputError) as error:
        ScenarioService(FakeSession()).create(request)

    assert any(item["reason"] == "mixed_territory_scope" for item in error.value.errors)
    assert not repository.persisted


def test_scenario_service_infers_legacy_municipal_scope_when_level_omitted(monkeypatch):
    repository = FakeRepository(level="municipality")
    result, session = _exercise_service(
        monkeypatch, repository, _request([repository.predictions[0].territory_id])
    )

    assert result.model_run_id == MODEL_ID
    assert result.level == "municipality"
    assert session.committed
    assert repository.persisted
