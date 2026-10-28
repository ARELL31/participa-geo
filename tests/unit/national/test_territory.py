from datetime import date
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest
from pydantic import ValidationError

from participa_geo.api.schemas.history import HistoryDTO
from participa_geo.api.schemas.models import ModelDTO, PredictionDTO
from participa_geo.api.schemas.scenarios import ScenarioRequest
from participa_geo.api.schemas.territories import TerritoryDTO
from participa_geo.territory import (
    TerritoryKey,
    observation_id,
    territory_id,
    validate_scenario_territories,
)


def test_territory_id_differs_by_level_and_district_plan() -> None:
    municipality = TerritoryKey("municipality", "14", "001")
    district_2021 = TerritoryKey("federal_district", "14", "01", "DERFE2021")
    district_2023 = TerritoryKey("federal_district", "14", "01", "DERFE2023")

    assert (
        len({territory_id(municipality), territory_id(district_2021), territory_id(district_2023)})
        == 3
    )


def test_municipality_rejects_district_plan() -> None:
    with pytest.raises(ValueError, match="municipality.*district_plan"):
        TerritoryKey("municipality", "14", "001", "DERFE2023")


def test_district_requires_plan() -> None:
    with pytest.raises(ValueError, match="district_plan"):
        TerritoryKey("federal_district", "14", "01")


def test_observation_id_includes_dataset_and_plan() -> None:
    source_one = UUID("00000000-0000-0000-0000-000000000001")
    source_two = UUID("00000000-0000-0000-0000-000000000002")
    district_2021 = TerritoryKey("federal_district", "14", "01", "DERFE2021")
    district_2023 = TerritoryKey("federal_district", "14", "01", "DERFE2023")

    assert observation_id(district_2021, 2024, source_one) != observation_id(
        district_2023, 2024, source_one
    )
    assert observation_id(district_2023, 2024, source_one) != observation_id(
        district_2023, 2024, source_two
    )


def test_legacy_jalisco_ids_preserved() -> None:
    legacy_territory = uuid5(NAMESPACE_URL, "ine:14:municipality:001:2025-12-15")
    legacy_observation = uuid5(
        NAMESPACE_URL,
        "ccpc:14:municipality:001:2024:dataset:00000000-0000-0000-0000-000000000001",
    )
    dataset = UUID("00000000-0000-0000-0000-000000000001")
    key = TerritoryKey("municipality", "14", "001")

    assert territory_id(key) == legacy_territory
    assert observation_id(key, 2024, dataset) == legacy_observation


def test_mixed_level_scenario_rejected() -> None:
    with pytest.raises(ValueError, match="same level"):
        validate_scenario_territories(
            [
                TerritoryKey("municipality", "14", "001"),
                TerritoryKey("federal_district", "14", "01", "DERFE2023"),
            ]
        )


def test_legacy_jalisco_dtos_remain_valid_with_additive_level_fields() -> None:
    territory = TerritoryDTO(
        id=uuid5(NAMESPACE_URL, "ine:14:municipality:001:2025-12-15"),
        name="Guadalajara",
        state_code="14",
        municipality_code="001",
        identity_status="verified_catalogue",
        footprint_status="not_verified",
        reference_date=date(2025, 12, 15),
    )
    history = HistoryDTO(year=2024, municipality_code="001", ln=10, sv=5, nv=4, ns=1, eligible=True)
    prediction = PredictionDTO(
        territory_id=territory.id,
        municipality_code="001",
        municipality_name="Guadalajara",
        target_year=2027,
        eligible=False,
        model_run_id=UUID("00000000-0000-0000-0000-000000000003"),
    )
    model = ModelDTO(
        model_run_id=prediction.model_run_id,
        family="M0",
        target_year=2027,
        reference_date="2025-12-15",
    )
    scenario = ScenarioRequest(
        model_run_id=prediction.model_run_id,
        target_year=2027,
        territory_ids=[territory.id],
        reduction_pp=1,
        assumption_code="preventive_exploration",
    )

    assert territory.municipality_code == "001"
    assert history.level == "municipality"
    assert prediction.district_plan is None
    assert model.level == "municipality"
    assert scenario.level is None


def test_scenario_level_is_optional_but_typed() -> None:
    with pytest.raises(ValidationError):
        ScenarioRequest(
            model_run_id=UUID("00000000-0000-0000-0000-000000000003"),
            target_year=2027,
            territory_ids=[UUID("00000000-0000-0000-0000-000000000004")],
            reduction_pp=1,
            assumption_code="preventive_exploration",
            level="county",
        )


def test_openapi_dtos_publish_additive_level_contract() -> None:
    territory_schema = TerritoryDTO.model_json_schema()
    history_schema = HistoryDTO.model_json_schema()
    prediction_schema = PredictionDTO.model_json_schema()
    model_schema = ModelDTO.model_json_schema()
    scenario_schema = ScenarioRequest.model_json_schema()

    for schema in (territory_schema, history_schema, prediction_schema):
        assert {"level", "territory_code", "district_plan"} <= set(schema["properties"])
    assert {"level", "district_plan"} <= set(model_schema["properties"])
    assert "level" in scenario_schema["properties"]
    assert "municipality_code" in territory_schema["properties"]
