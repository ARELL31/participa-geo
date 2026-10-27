"""Integration tests for the real temporal training pipeline.

These use the real processed observations (``data/processed``) and the identity
statuses read from PostGIS (T3). They verify the actual candidate count (85 for
2027, computed from quality + identity — not hardcoded), the 125 prediction
records including the insufficient ones, determinism (same family/id/exclusions,
values within 1e-8), and that mutating the 2024 target does not change the
family chosen on 2021.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from participa_geo.ingestion.schema import MunicipalObservation

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSED = REPO_ROOT / "data" / "processed"


def _load(postgis_session):
    from participa_geo.db.repository import read_processed_observations
    from participa_geo.prediction.cohorts import read_identity_statuses

    identity = read_identity_statuses(postgis_session)
    _, observations = read_processed_observations(PROCESSED)
    return identity, observations


def test_read_identity_statuses_complete(postgis_session):
    from participa_geo.prediction.cohorts import read_identity_statuses

    identity = read_identity_statuses(postgis_session)
    assert len(identity) == 125
    for ident in identity.values():
        assert ident.identity_status.value == "verified_catalogue"


def test_train_release_reproducible(postgis_session, tmp_path):
    from participa_geo.prediction.training import train_release

    identity, observations = _load(postgis_session)
    first = train_release(observations, tmp_path / "a", identity_statuses=identity)
    second = train_release(observations, tmp_path / "b", identity_statuses=identity)

    assert first.family == second.family
    assert first.model_run_id == second.model_run_id
    assert first.candidate_count == second.candidate_count
    assert [p.municipality_code for p in first.predictions] == [
        p.municipality_code for p in second.predictions
    ]
    assert [e.municipality_code for e in first.exclusions] == [
        e.municipality_code for e in second.exclusions
    ]
    for p1, p2 in zip(first.predictions, second.predictions, strict=True):
        if p1.estimated_abstention_pct is None:
            assert p2.estimated_abstention_pct is None
        else:
            assert p1.estimated_abstention_pct == pytest.approx(
                p2.estimated_abstention_pct, rel=0, abs=1e-8
            )


def test_train_release_85_candidates_125_records(postgis_session, tmp_path):
    from participa_geo.prediction.training import train_release

    identity, observations = _load(postgis_session)
    bundle = train_release(observations, tmp_path, identity_statuses=identity)

    assert bundle.candidate_count == 85
    assert len(bundle.predictions) == 125

    insufficient = [p for p in bundle.predictions if p.risk == "insufficient"]
    assert len(insufficient) == 125 - 85

    for name in (
        "model.json",
        "evaluation.json",
        "predictions-2027.parquet",
        "exclusions.csv",
        "manifest.json",
    ):
        assert (tmp_path / name).exists()


def test_identity_status_and_candidate_evidence_change_model_run_id(
    postgis_session, tmp_path
):
    from participa_geo.ingestion.schema import FootprintStatus, IdentityStatus
    from participa_geo.prediction.cohorts import TerritoryIdentity
    from participa_geo.prediction.training import train_release

    identity, observations = _load(postgis_session)
    baseline = train_release(
        observations, tmp_path / "base-id", identity_statuses=identity
    )
    eligible_code = next(
        prediction.municipality_code
        for prediction in baseline.predictions
        if prediction.eligible
    )
    changed = dict(identity)
    changed[eligible_code] = TerritoryIdentity(
        IdentityStatus.known_changed, FootprintStatus.not_verified
    )
    altered = train_release(
        observations, tmp_path / "altered-id", identity_statuses=changed
    )
    assert altered.model_run_id != baseline.model_run_id
    assert altered.candidate_count < baseline.candidate_count


def test_evaluation_persists_2024_errors_and_empirical_coverage(
    postgis_session, tmp_path
):
    from participa_geo.prediction.training import train_release

    identity, observations = _load(postgis_session)
    bundle = train_release(
        observations, tmp_path / "coverage", identity_statuses=identity
    )
    band = bundle.evaluation_payload["band"]
    assert band["amplitude_pp"] == pytest.approx(8.561771770259021)
    assert len(band["errors_2021"]) == 91
    assert len(band["errors_2024"]) == 75
    coverage = band["empirical_coverage_2024"]
    assert coverage is not None
    assert coverage["n"] == 75
    assert 0 <= coverage["within"] <= coverage["n"]
    assert coverage["share"] == pytest.approx(coverage["within"] / coverage["n"])
    assert coverage["amplitude_pp"] == band["amplitude_pp"]
    assert (tmp_path / "coverage" / "exclusions-by-cut.csv").is_file()


def test_mutating_2024_target_keeps_selection(postgis_session, tmp_path):
    from participa_geo.prediction.training import train_release

    identity, observations = _load(postgis_session)
    baseline = train_release(observations, tmp_path / "base", identity_statuses=identity)

    # Swap SV/NV for 2024 only: preserves accounting and quality, but changes the
    # 2024 abstention target (and thus the final 2027 fit), never the 2021 choice.
    mutated: list[MunicipalObservation] = []
    for obs in observations:
        if obs.year == 2024:
            mutated.append(
                MunicipalObservation(
                    key=obs.key,
                    year=obs.year,
                    ln=obs.ln,
                    sv=obs.nv,
                    nv=obs.sv,
                    ns=obs.ns,
                    municipality_name=obs.municipality_name,
                    young_share=obs.young_share,
                    senior_share=obs.senior_share,
                    rural_share=obs.rural_share,
                    source_version_id=obs.source_version_id,
                )
            )
        else:
            mutated.append(obs)

    changed = train_release(mutated, tmp_path / "changed", identity_statuses=identity)
    assert changed.family == baseline.family
