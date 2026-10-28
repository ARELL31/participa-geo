from __future__ import annotations

from participa_geo.ingestion.continuity import (
    SectionFactCount,
    aggregate_municipality_district_year,
    build_continuity,
    build_municipality_district_bridge,
    district_coverage,
    reconstruct_district_2023,
    validate_2023_reference,
)


def _history(section, **overrides):
    row = {
        "cve_ent": "01",
        "seccion": str(section),
        "Distrito_PEF2009": "01",
        "Distrito_PEF2012": "01",
        "Distrito_PEF2015": "01",
        "Distrito_PEF2018": "01",
        "Distrito_PEF2021": "01",
        "Nueva_Dttacion_2023": "01",
        "Distrito_PEF2024": "01",
        "seccion_alta": "",
        "seccion_baja": "",
        "seccion_movim_parcial": "",
        "cambio_dtto": "",
        "cambio_mpio": "",
        "PRIMER_MOVIMIENTO": "",
        "SEGUNDO_MOVIMIENTO": "",
        "TERCER_MOVIMIENTO": "",
    }
    row.update(overrides)
    return row


def _fact(
    year, section, ln, district_2021="01", district_2023=None, municipality="001", state="01"
):
    return SectionFactCount(
        year=year,
        state_code=state,
        municipality_code=municipality,
        section=str(section),
        district_2021=district_2021,
        district_2023=district_2023,
        ln=ln,
        sv=ln // 2,
        nv=ln // 4,
        ns=ln - ln // 2 - ln // 4,
    )


def test_2024_reference_uses_official_plan_column_and_matches_ccpc_and_mgs():
    historical = [_history(1, Nueva_Dttacion_2023="01", Distrito_PEF2024="01")]
    mgs = [{"state_code": "01", "municipality_code": "001", "section": "1", "district_2023": "01"}]
    ccpc = [_fact(2024, 1, 100, district_2021=None, district_2023="01")]

    audit = validate_2023_reference(historical, mgs, ccpc)

    assert audit.column == "Nueva_Dttacion_2023"
    assert audit.common_section_count == 1
    assert audit.ccpc_mismatches == 0
    assert audit.mgs_mismatches == 0


def test_official_movement_maps_old_section_to_target_without_number_join():
    historical = [
        _history(10),
        _history(
            9,
            Nueva_Dttacion_2023="",
            Distrito_PEF2021="02",
            seccion_baja="X",
            PRIMER_MOVIMIENTO="BAJA POR INTEGRACION SECCIONAL 2023 (SE FUSIONA A LA SECCION 0010)",
        ),
    ]
    mgs = [{"state_code": "01", "municipality_code": "001", "section": "10", "district_2023": "01"}]
    facts = [_fact(2021, 9, 50, district_2021="02")]

    report = build_continuity(historical, mgs, facts, source_year=2021)

    matched = [link for link in report.links if link.status == "matched"]
    assert [(link.source_section, link.target_section) for link in matched] == [("9", "10")]
    assert "FUSIONA" in matched[0].evidence.upper()


def test_official_2018_plan_field_is_required_for_historical_mapping():
    historical = [_history(25, Distrito_PEF2018="03", Nueva_Dttacion_2023="04")]
    mgs = [{"state_code": "01", "municipality_code": "001", "section": "25", "district_2023": "04"}]
    facts = [_fact(2018, 25, 80, district_2021="03")]

    report = build_continuity(historical, mgs, facts, source_year=2018)

    assert report.matched_count == 1
    assert report.links[0].target_district == "04"
    assert "Distrito_PEF2018" in report.links[0].evidence


def test_section_without_validated_history_remains_unmatched():
    facts = [_fact(2018, 88, 40)]

    report = build_continuity([], [], facts, source_year=2018)

    assert len(report.links) == 1
    assert report.links[0].status == "unmatched"
    assert report.links[0].target_section is None


def test_blank_ccpc_def_is_not_imputed_from_historical_catalogue():
    historical = [_history(88)]
    mgs = [{"state_code": "01", "municipality_code": "001", "section": "88", "district_2023": "01"}]
    facts = [_fact(2009, 88, 40, district_2021=None)]

    report = build_continuity(historical, mgs, facts, source_year=2009)

    assert report.links[0].status == "unmatched"
    assert report.links[0].target_district is None


def test_coverage_uses_2024_reference_ln_and_both_gates():
    reference = [
        _fact(2024, 1, 95, district_2021=None, district_2023="01"),
        _fact(2024, 2, 5, district_2021=None, district_2023="02"),
    ]
    continuity = [
        type(
            "Link",
            (),
            {
                "source_year": 2018,
                "state_code": "01",
                "source_section": "1",
                "target_section": "1",
                "status": "matched",
            },
        )(),
    ]

    coverage = district_coverage(reference, continuity, district_codes={("01", "01"), ("01", "02")})
    by_district = {item.district_code: item for item in coverage}

    assert by_district["01"].reference_ln == 95
    assert by_district["01"].matched_ln == 95
    assert by_district["01"].status == "insufficient"
    assert by_district["01"].district_gate_passed is True
    assert by_district["01"].national_gate_passed is False
    assert by_district["02"].coverage == 0
    assert by_district["02"].status == "insufficient"
    national = next(item for item in coverage if item.district_code == "ALL")
    assert national.reference_ln == 100
    assert national.matched_ln == 95
    assert national.coverage == 0.95
    assert national.national_threshold == 0.98
    assert national.status == "insufficient"


def test_new_district_is_eligible_only_with_coverage():
    reference = [_fact(2024, 1, 100, district_2021=None, district_2023="09")]
    absent = district_coverage(reference, [], district_codes={("01", "09")})[0]
    matched = district_coverage(
        reference,
        [
            type(
                "Link",
                (),
                {
                    "source_year": 2021,
                    "state_code": "01",
                    "source_section": "11",
                    "target_section": "1",
                    "status": "matched",
                },
            )()
        ],
        district_codes={("01", "09")},
    )[0]

    assert absent.status == "insufficient"
    assert matched.status == "eligible"


def test_seven_new_numbers_are_not_given_historical_district_identity():
    new_districts = {
        ("02", "09"),
        ("05", "08"),
        ("19", "13"),
        ("19", "14"),
        ("21", "16"),
        ("22", "06"),
        ("31", "06"),
    }
    reference = [
        _fact(2024, index, 100, district_2021=None, district_2023=district, state=state)
        for index, (state, district) in enumerate(sorted(new_districts), 1)
    ]
    # These section facts deliberately have no continuity links: eligibility is
    # decided by validated coverage, never by district number novelty alone.
    coverage = district_coverage(reference, [], district_codes=new_districts)

    assert len([row for row in coverage if row.district_code != "ALL"]) == 7
    assert all(row.status == "insufficient" for row in coverage if row.district_code != "ALL")


def test_bridge_preserves_split_municipality_pairs_from_mgs():
    mgs = [
        {"state_code": "01", "municipality_code": "001", "section": "1", "district_2023": "01"},
        {"state_code": "01", "municipality_code": "001", "section": "2", "district_2023": "02"},
    ]

    bridge = build_municipality_district_bridge(mgs)

    assert {(row.municipality_code, row.district_code) for row in bridge} == {
        ("001", "01"),
        ("001", "02"),
    }
    assert all(row.is_split for row in bridge)


def test_reconstruction_keeps_2021_plan_separate_from_2023_plan():
    facts = [_fact(2021, 1, 100, district_2021="07")]
    continuity = [
        type(
            "Link",
            (),
            {
                "source_year": 2021,
                "state_code": "01",
                "source_section": "1",
                "target_section": "1",
                "target_district": "02",
                "status": "matched",
                "evidence": "official stable section record",
            },
        )()
    ]
    mgs = [{"state_code": "01", "municipality_code": "001", "section": "1", "district_2023": "02"}]

    observations = reconstruct_district_2023(facts, continuity, mgs)

    assert len(observations) == 1
    assert observations[0].district_plan == "DERFE2023"
    assert observations[0].district_code == "02"
    assert observations[0].district_code != facts[0].district_2021


def test_district_aggregates_sum_to_mapped_section_counts():
    facts = [
        _fact(2018, 1, 60, district_2021="01"),
        _fact(2018, 2, 40, district_2021="02"),
    ]
    continuity = [
        type(
            "Link",
            (),
            {
                "source_year": 2018,
                "state_code": "01",
                "source_section": "1",
                "target_section": "11",
                "target_district": "01",
                "status": "matched",
                "evidence": "official",
            },
        )(),
        type(
            "Link",
            (),
            {
                "source_year": 2018,
                "state_code": "01",
                "source_section": "2",
                "target_section": "22",
                "target_district": "02",
                "status": "matched",
                "evidence": "official",
            },
        )(),
    ]
    mgs = [
        {"state_code": "01", "municipality_code": "001", "section": "11", "district_2023": "01"},
        {"state_code": "01", "municipality_code": "002", "section": "22", "district_2023": "02"},
    ]

    observations = reconstruct_district_2023(facts, continuity, mgs)

    assert sum(row.ln for row in observations) == 100
    assert sum(row.section_count for row in observations) == 2

    intersections = aggregate_municipality_district_year(facts, continuity, mgs)
    assert sum(row.ln for row in intersections) == sum(row.ln for row in observations)
    assert {(row.municipality_code, row.district_code) for row in intersections} == {
        ("001", "01"),
        ("002", "02"),
    }
