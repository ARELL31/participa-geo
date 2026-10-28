"""Database load for the validated national section-fact artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from participa_geo.db.session import writer_engine
from participa_geo.ingestion.national import resolve_current_generation
from participa_geo.settings import Settings

FACT_COLUMNS = (
    "year",
    "state_code",
    "municipality_code",
    "section",
    "district_2021",
    "district_2023",
    "sex",
    "age",
    "section_type",
    "state_name",
    "municipality_name",
    "ln",
    "sv",
    "nv",
    "ns",
    "dataset_version_id",
    "source_row",
    "source_hash",
    "source_state_code",
    "source_municipality_code",
    "source_district",
)


def load_national_facts(processed_dir: Path, settings: Settings | None = None) -> int:
    """Atomically replace national section facts using PostgreSQL COPY streaming."""
    from pyarrow import parquet

    settings = settings or Settings()
    processed_dir = resolve_current_generation(Path(processed_dir))
    manifest = json.loads((processed_dir / "national-ingest.json").read_text())
    source_rows = []
    for source in manifest["sources"]:
        for member in source["csv_members"]:
            if member["state_code"] is None:
                continue
            source_rows.append(
                (
                    member["dataset_version_id"],
                    source["year"],
                    member["state_code"],
                    source["source_url"],
                    member["member"],
                    member["sha256"],
                    "utf-8-sig",
                )
            )

    engine = writer_engine(settings)
    row_count = 0
    try:
        with engine.begin() as connection:
            raw = connection.connection.driver_connection
            with raw.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO dataset_version "
                    "(id,year,state_code,source_url,member,sha256,encoding) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (id) DO UPDATE SET source_url=EXCLUDED.source_url, "
                    "member=EXCLUDED.member, sha256=EXCLUDED.sha256, "
                    "state_code=EXCLUDED.state_code",
                    source_rows,
                )
                cursor.execute("TRUNCATE TABLE fact_ccpc_section")
                columns = ",".join(FACT_COLUMNS)
                statement = f"COPY fact_ccpc_section ({columns}) FROM STDIN"
                for year in (2009, 2012, 2015, 2018, 2021, 2024):
                    parquet_file = parquet.ParquetFile(
                        processed_dir / f"ccpc-section-{year}.parquet"
                    )
                    with cursor.copy(statement) as copy:
                        for batch in parquet_file.iter_batches(batch_size=10_000):
                            for values in batch.select(FACT_COLUMNS).to_pylist():
                                values["year"] = int(values["year"])
                                values["age"] = int(values["age"])
                                values["dataset_version_id"] = UUID(values["dataset_version_id"])
                                copy.write_row(tuple(values[column] for column in FACT_COLUMNS))
                                row_count += 1
                if row_count != manifest["row_count"]:
                    raise ValueError(
                        f"database COPY row count {row_count} != manifest "
                        f"{manifest['row_count']}"
                    )
    finally:
        engine.dispose()
    return row_count


__all__ = ["load_national_facts"]
