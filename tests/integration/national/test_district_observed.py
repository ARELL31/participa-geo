from __future__ import annotations

from sqlalchemy import text

from participa_geo.db.repository import Repository


def test_district_history_uses_complete_ccpc_totals_and_separate_mgs_coverage(
    postgis_session,
):
    postgis_session.execute(
        text(
            "INSERT INTO agg_district_year "
            "(year,state_code,district_code,district_plan,section_count,ln,sv,nv,ns) "
            "VALUES (2024,'98','01','DERFE2023',3,150,75,50,25)"
        )
    )
    postgis_session.execute(
        text(
            "INSERT INTO agg_municipality_district_year "
            "(year,state_code,municipality_code,district_code,district_plan,section_count,"
            "ln,sv,nv,ns,coverage_status) "
            "VALUES (2024,'98','001','01','DERFE2023',2,100,50,30,20,'insufficient')"
        )
    )
    postgis_session.execute(
        text(
            "INSERT INTO district_reconstruction_coverage "
            "(year,state_code,district_code,matched_ln,reference_ln,coverage,status,"
            "reference_section_count,matched_section_count,unmatched_ccpc_section_count,"
            "unmatched_ccpc_ln,ccpc_without_mgs_section_count,ccpc_without_mgs_ln,"
            "mgs_only_section_count,mgs_only_ln,section_universe_gap_count,district_plan) "
            "VALUES (2024,'98','01',100,150,0.6666666666666666,'insufficient',"
            "3,2,1,50,1,50,0,0,1,'DERFE2023')"
        )
    )

    records, total = Repository(postgis_session).get_history(
        territory_id=None,
        year=2024,
        page=1,
        page_size=10,
        level="federal_district",
        state_code="98",
    )

    assert total == 1
    assert len(records) == 1
    assert (records[0].ln, records[0].sv, records[0].nv, records[0].ns) == (150, 75, 50, 25)
    assert records[0].coverage_share == 0.6666666666666666
    assert records[0].eligible is False
