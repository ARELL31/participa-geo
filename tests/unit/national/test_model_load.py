"""Regression coverage for national prediction artifact field compatibility."""


def test_missing_optional_risk_unstable_defaults_false():
    from participa_geo.db.repository import _optional_bool

    assert _optional_bool({}, "risk_unstable", default=False) is False
    assert _optional_bool({"risk_unstable": True}, "risk_unstable", default=False) is True


def test_national_observation_reader_preserves_dataset_identity_and_zero_pads(tmp_path):
    import csv
    import json

    from participa_geo.db.repository import read_national_municipal_observations

    with (tmp_path / "municipal-observations.csv").open("w", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(
            [
                "year", "state_code", "municipality_code", "municipality_name",
                "ln", "sv", "nv", "ns", "young_share", "senior_share",
                "rural_share", "source_version_ids",
            ]
        )
        writer.writerow(
            [2024, 14, 1, "Test municipio", 100, 40, 50, 10, 0.2, 0.1, 0.3,
             json.dumps(["00000000-0000-0000-0000-000000000001"])]
        )

    observations = read_national_municipal_observations(tmp_path)

    assert len(observations) == 1
    assert observations[0].key.state_code == "14"
    assert observations[0].key.municipality_code == "001"
    assert observations[0].source_version_id.hex == "00000000000000000000000000000001"
