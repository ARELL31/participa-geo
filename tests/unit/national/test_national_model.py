from __future__ import annotations

from copy import deepcopy

import pytest

from participa_geo.ingestion.schema import (
    FootprintStatus,
    IdentityStatus,
    MunicipalityKey,
    MunicipalObservation,
)
from participa_geo.prediction.artifacts import compute_model_run_id
from participa_geo.prediction.cohorts import TerritoryIdentity
from participa_geo.prediction.national import build_national_cohort, train_national


def _observation(state: str, code: str, year: int) -> MunicipalObservation:
    return MunicipalObservation(
        key=MunicipalityKey(state, code),
        year=year,
        ln=1200,
        sv=800,
        nv=300,
        ns=100,
        municipality_name=f"{state}-{code}",
        young_share=0.2,
        senior_share=0.15,
        rural_share=0.4,
    )


def _identity(status=IdentityStatus.verified_catalogue):
    return TerritoryIdentity(status, FootprintStatus.not_verified)


def test_national_cohort_requires_explicit_identity_for_each_state_municipality():
    observations = [_observation("01", "001", year) for year in (2021, 2024)]

    with pytest.raises(ValueError, match="identity"):
        build_national_cohort(observations, 2027, {})


def test_national_cohort_uses_full_key_and_excludes_unverified_identity():
    observations = [
        _observation(state, "001", year) for state in ("01", "02") for year in (2021, 2024)
    ]
    identities = {("01", "001"): _identity(), ("02", "001"): _identity(IdentityStatus.ambiguous)}

    cohort = build_national_cohort(observations, 2027, identities)

    assert [(row.state_code, row.municipality_code) for row in cohort.rows] == [("01", "001")]
    assert [(row.state_code, row.municipality_code) for row in cohort.exclusions] == [("02", "001")]


def test_national_cohort_keeps_low_quality_municipality_excluded_not_zero():
    observations = [
        _observation("01", "001", 2021),
        _observation("01", "001", 2024),
        _observation("01", "002", 2021),
        MunicipalObservation(
            key=MunicipalityKey("01", "002"),
            year=2024,
            ln=100,
            sv=60,
            nv=30,
            ns=10,
            municipality_name="small",
            young_share=0.2,
            senior_share=0.15,
            rural_share=0.4,
        ),
    ]
    identities = {("01", code): _identity() for code in ("001", "002")}

    cohort = build_national_cohort(observations, 2027, identities)

    insufficient = next(row for row in cohort.exclusions if row.municipality_code == "002")
    assert "small_known_count" in insufficient.reasons


def test_national_training_uses_state_fixed_effects_and_emits_insufficient_rows(tmp_path):
    observations = []
    identities = {}
    for number in range(40):
        state, code = f"{number % 32 + 1:02d}", f"{number + 1:03d}"
        identities[(state, code)] = _identity()
        for year in (2009, 2012, 2015, 2018, 2021, 2024):
            known = 1200 + number * 10
            nv = 250 + (number % 13) * 5
            observations.append(
                MunicipalObservation(
                    key=MunicipalityKey(state, code),
                    year=year,
                    ln=known + 50,
                    sv=known - nv,
                    nv=nv,
                    ns=50,
                    municipality_name=f"{state}-{code}",
                    young_share=0.15 + (number % 5) / 100,
                    senior_share=0.1 + (number % 7) / 100,
                    rural_share=0.2 + (number % 9) / 100,
                )
            )
    # Explicit catalog universe includes a territory with no history; it must be null.
    identities[("32", "999")] = _identity()

    bundle = train_national(observations, output_dir=tmp_path, identity_statuses=identities)

    assert bundle.level == "municipality"
    assert bundle.total_count == 41
    assert bundle.candidate_count == sum(p.eligible for p in bundle.predictions)
    assert bundle.model_payload["fixed_effect_states"] == [f"{n:02d}" for n in range(2, 33)]
    state_metrics = bundle.evaluation_payload["state_metrics"]
    for family in ("m0", "m1"):
        for year in ("2021", "2024"):
            assert state_metrics[family][year]
            for metrics in state_metrics[family][year].values():
                assert set(metrics) == {"mae", "rmse", "bias", "n"}
                assert metrics["n"] > 0
    insufficient = next(p for p in bundle.predictions if p.municipality_code == "999")
    assert insufficient.estimate is None
    assert insufficient.risk == "insufficient"
    assert (tmp_path / "predictions-2027.parquet").is_file()
    assert (tmp_path / "exclusions-by-cut.csv").is_file()

    changed_2024 = [
        MunicipalObservation(
            key=o.key,
            year=o.year,
            ln=o.ln,
            sv=o.sv - 50 if o.year == 2024 else o.sv,
            nv=o.nv + 50 if o.year == 2024 else o.nv,
            ns=o.ns,
            municipality_name=o.municipality_name,
            young_share=o.young_share,
            senior_share=o.senior_share,
            rural_share=o.rural_share,
        )
        for o in observations
    ]
    changed = train_national(changed_2024, identity_statuses=identities)
    assert changed.family == bundle.family
    assert changed.evaluation_payload["selection"] == bundle.evaluation_payload["selection"]
    assert changed.model_run_id != bundle.model_run_id


def test_national_training_rejects_district_level():
    with pytest.raises(ValueError, match="municipality only"):
        train_national([], level="federal_district", identity_statuses={})


def test_2021_m1_fit_and_validation_metrics_are_in_hashed_model_identity(monkeypatch):
    from participa_geo.prediction import national

    observations = []
    identities = {}
    for number in range(40):
        state, code = f"{number % 32 + 1:02d}", f"{number + 1:03d}"
        identities[(state, code)] = _identity()
        for year in (2009, 2012, 2015, 2018, 2021, 2024):
            nv = 250 + number % 20
            observations.append(
                MunicipalObservation(
                    key=MunicipalityKey(state, code),
                    year=year,
                    ln=1250,
                    sv=950 - number % 20,
                    nv=nv,
                    ns=50,
                    municipality_name=f"{state}-{code}",
                    young_share=0.2,
                    senior_share=0.1,
                    rural_share=0.4,
                )
            )

    captured_identity = {}
    original_compute = national.compute_model_run_id

    def capture_identity(identity):
        captured_identity.update(deepcopy(identity))
        return original_compute(identity)

    monkeypatch.setattr(national, "compute_model_run_id", capture_identity)
    bundle = train_national(observations, identity_statuses=identities)

    candidate = captured_identity["candidate_m1_2021"]
    assert candidate["metrics"] == bundle.evaluation_payload["metrics"]["m1"]["2021"]
    changed_identity = deepcopy(captured_identity)
    changed_identity["candidate_m1_2021"]["coefficients"][0] += 0.01
    assert compute_model_run_id(changed_identity) != bundle.model_run_id


def test_national_training_builds_and_consumes_mgs_identity_statuses(monkeypatch):
    from pipelines.training import national as pipeline

    observations = []
    identities = {}
    for number in range(40):
        state, code = f"{number % 32 + 1:02d}", f"{number + 1:03d}"
        identities[(state, code)] = _identity()
        for year in (2009, 2012, 2015, 2018, 2021, 2024):
            nv = 250 + number % 20
            observations.append(
                MunicipalObservation(
                    key=MunicipalityKey(state, code),
                    year=year,
                    ln=1250,
                    sv=950 - number % 20,
                    nv=nv,
                    ns=50,
                    municipality_name=f"{state}-{code}",
                    young_share=0.2,
                    senior_share=0.1,
                    rural_share=0.4,
                )
            )
    build_calls = []
    monkeypatch.setattr(pipeline, "read_national_municipal_observations", lambda _: observations)
    monkeypatch.setattr(
        pipeline,
        "build_national_municipal_identity",
        lambda session, rows: (
            build_calls.append((session, rows)) or type("Audit", (), {"reference_count": 2477})()
        ),
    )
    monkeypatch.setattr(pipeline, "read_national_identity_statuses", lambda _: identities)

    bundle = pipeline.train_national_municipal("ignored", "ignored", session="session")

    assert build_calls == [("session", observations)]
    assert bundle.total_count == 40
    assert all(pred.identity_status == "verified_catalogue" for pred in bundle.predictions)
