"""Guard the set-based latest-version predicate used in national history reads."""

from sqlalchemy import text

from participa_geo.db.repository import _LATEST_VERSION_FOR_YEAR


def test_latest_versions_are_selected_once_per_state_and_observation_year():
    # The selected year is observation.year, not dataset_version.year; choosing
    # versions once avoids the previous correlated scan for every outer row.
    assert "DISTINCT ON (dv2.state_code, o2.year)" in _LATEST_VERSION_FOR_YEAR
    assert "o2.year = o.year" not in _LATEST_VERSION_FOR_YEAR
    assert "dv2.state_code = dv.state_code" not in _LATEST_VERSION_FOR_YEAR


def test_latest_version_ties_use_created_at_then_id():
    assert "ORDER BY dv2.state_code, o2.year, dv2.created_at DESC, dv2.id DESC" in (
        _LATEST_VERSION_FOR_YEAR
    )


def test_latest_versions_are_per_state_and_observation_year(postgis_session):
    # Isolated VALUES CTEs exercise the production predicate without inserting
    # synthetic rows into the shared test database.
    rows = postgis_session.execute(
        text(f"""
            WITH dataset_version(id, state_code, created_at) AS (
                VALUES
                  ('00000000-0000-0000-0000-000000000001'::uuid, '14', '2020-01-01'::timestamptz),
                  ('00000000-0000-0000-0000-000000000002'::uuid, '14', '2020-01-02'::timestamptz),
                  ('00000000-0000-0000-0000-000000000003'::uuid, '19', '2020-01-03'::timestamptz),
                  ('00000000-0000-0000-0000-000000000004'::uuid, '14', '2020-01-04'::timestamptz),
                  ('00000000-0000-0000-0000-000000000005'::uuid, '14', '2020-01-02'::timestamptz),
                  ('00000000-0000-0000-0000-000000000006'::uuid, NULL, '2020-01-05'::timestamptz)
            ), observation(dataset_version_id, year) AS (
                VALUES
                  ('00000000-0000-0000-0000-000000000001'::uuid, 2020),
                  ('00000000-0000-0000-0000-000000000002'::uuid, 2020),
                  ('00000000-0000-0000-0000-000000000003'::uuid, 2020),
                  ('00000000-0000-0000-0000-000000000005'::uuid, 2020),
                  ('00000000-0000-0000-0000-000000000005'::uuid, 2021),
                  ('00000000-0000-0000-0000-000000000006'::uuid, 2020)
            )
            SELECT dv.id::text
            FROM observation o
            JOIN dataset_version dv ON dv.id = o.dataset_version_id
            WHERE {_LATEST_VERSION_FOR_YEAR}
            ORDER BY dv.id
        """)
    ).scalars().all()

    assert rows == [
        "00000000-0000-0000-0000-000000000003",  # state 19, year 2020
        "00000000-0000-0000-0000-000000000005",  # tie by id, state 14/year 2020
        "00000000-0000-0000-0000-000000000005",  # partial latest, state 14/year 2021
    ]
