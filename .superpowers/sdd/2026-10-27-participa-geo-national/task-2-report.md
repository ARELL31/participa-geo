# Task 2 report — National section ingestion and municipal aggregates

**Status: DONE_WITH_CONCERNS**

**Commit:** `fdd6d8c feat: ingest national CCPC section facts and municipal aggregates`

## Implementation

- Added a formal, streaming CSV reader for all six CCPC ZIP archives. It enforces
  the exact 16-column header, codes/ranges, `LN=SV+NV+NS`, and uniqueness of
  `(state, municipality, section, sex, age)`. Oaxaca quoted/comma names are
  parsed by Python's CSV parser. Original state, municipality, and `DEF` text,
  source row, and per-member SHA-256 are retained alongside normalized codes.
- Added `fact_ccpc_section` with six year partitions and indexes. `DEF` maps to
  `district_2021` for 2009–2021 and `district_2023` for 2024; blank values remain
  NULL. Dataset-version identity includes state, year, and CSV SHA-256.
- Added streaming Parquet section-fact outputs, municipal sums/shares and quality
  flags, a deterministic national manifest with archive/member hashes, URLs and
  source Last-Modified values, plus transactional PostgreSQL COPY loading.
- Added CLI `ingest-national` with the requested defaults, source inventory, and
  methodology notes. It does not implement historical district reconstruction.

## Full-data evidence

Command (run twice):

```bash
sg docker -c 'docker compose run --rm --no-deps api python -m participa_geo.cli ingest-national --source-dir data/raw/ccpc-national --output-dir data/processed/national'
```

Both runs reported:

```text
ingested 54872712 section facts from 192 CSVs; 14779 municipal observations (2477 in 2024), 300 plan-versioned districts, 44154 blank DEF values; loaded 54872712 rows into PostGIS
```

Database read-back by year confirmed 32 states for each year and these row and
municipality counts:

| Year | Rows | Municipalities |
|---:|---:|---:|
| 2009 | 8,706,843 | 2,458 |
| 2012 | 8,604,456 | 2,455 |
| 2015 | 9,106,059 | 2,458 |
| 2018 | 9,251,122 | 2,463 |
| 2021 | 9,430,502 | 2,468 |
| 2024 | 9,773,730 | 2,477 |

The database check returned 300 distinct 2023-plan districts in 2024, zero
accounting mismatches, and 44,154 blank source `DEF` values (28,477 in 2009;
15,677 in 2012), with the corresponding 2021 district fields NULL. All 54,872,712
rows were loaded. The output manifest records 192 member hashes and six archive
hashes. The SHA-256 values of all eight output files were identical across the
two full runs.

## Verification

- RED: `python -m pytest tests/unit/national/test_national_ingestion.py -q`
  initially failed at collection because `ingestion.national` did not exist.
- GREEN/focused: `python -m pytest tests/unit/national/test_national_ingestion.py tests/unit/national/test_territory.py tests/unit/national/test_scenario_scope.py tests/unit/test_aggregation.py tests/unit/test_ccpc_schema.py -q`
  → **46 passed**.
- Migration integration: `python -m pytest tests/integration/national/test_migration_levels.py -q`
  → **2 passed**, including empty-schema migration chain, yearly partition parent,
  and writer COPY privileges.
- `ruff check` on Task 2 Python/migration/test files → **All checks passed**.
- `git diff --check` → no whitespace errors.
- Full suite `python -m pytest -q` → **137 passed, 21 failed, 82 errors**. Failures
  are existing baseline setup gaps: Jalisco processed/raw/model artifacts are
  missing (`municipal-observations.parquet`, `provenance.json`, predictions and
  model manifest), and GeoServer has no published Jalisco layers; downstream
  contract/integration/report tests consequently error. The two direct GeoServer
  assertions fail because the requested `municipalities` layer is unavailable.
  These are not counted as green and were not expanded into Task 2 scope.

## Concerns and rulings

1. Existing `data/sources.json` is the MVP/Jalisco manifest consumed by the legacy
   ingestion path. I left it unchanged and added `data/sources-national.json`;
   overwriting or changing the old manifest would break the separate MVP
   interface. This inventory lists URLs/Last-Modified, while exact archive and
   member SHA-256 values are generated in `national-ingest.json` from the staged
   official ZIPs. Archive contents were streamed and ZIP CRCs checked while
   reading CSV members.
2. During development, the first database COPY attempt found that writer lacked
   `TRUNCATE` permission on the new partitioned fact table. Migration 0005 grants
   writer the required SELECT/INSERT/DELETE/TRUNCATE permissions. The initial
   Task 2 migration also granted API SELECT; Fix round 1 removes that grant and
   the clean migration test asserts API has no SELECT. The local national DB was
   updated with the writer grants and API revoke before repeat ingestion.
3. Native input/processed outputs remain ignored and are not committed. No MVP
   worktree or volume was accessed.

## Changed files

- `apps/api/participa_geo/ingestion/national.py`
- `apps/api/participa_geo/ingestion/section_fact.py`
- `apps/api/participa_geo/db/models.py`
- `apps/api/participa_geo/cli.py`
- `pipelines/ingestion/national.py`
- `alembic/versions/0005_section_fact.py`
- `data/sources-national.json`
- `docs/methodology/national-ingestion.md`
- `tests/unit/national/test_national_ingestion.py`
- `tests/unit/national/test_national_generation.py`
- `tests/integration/national/test_migration_levels.py`

## Fix round 1

- Removed API `SELECT` on `fact_ccpc_section` from migration 0005, added a clean
  migration assertion for that privilege, and revoked it in the local national
  database. Direct privilege verification returned `false` for API SELECT.
- National artifacts now publish as immutable `generations/<generation_id>/`
  directories behind an atomically replaced `current.json` pointer. The DB
  loader resolves and verifies the generation manifest and artifact hashes.
  Regression tests cover failed publication preserving the previous pointer,
  successful generation switching, and artifact hash records.
- `data/sources-national.json` is now consumed as the authority for source URLs,
  retrieval/Last-Modified dates, local ZIP names, and expanded expected CSV member
  names. All six local archive SHA-256 values are computed and written into the
  generation manifest; declared hashes are enforced when provided. The inventory
  records the 2024 `tam.csv` suffix exception.
- Ingestion validates 32 distinct `EDOCVE` values in each archive.
- Focused ingestion/generation/migration tests: **16 passed**. Targeted Ruff and
  `git diff --check` passed. Archive inventory/member/hash validation passed for
  all six local ZIPs.

### Full-data repeatability verification

The CLI was run twice consecutively against the local ZIPs and national DB:

```bash
sg docker -c 'docker compose run --rm --no-deps api python -m participa_geo.cli ingest-national --source-dir data/raw/ccpc-national --output-dir data/processed/national --sources data/sources-national.json'
```

Both runs reported **54,872,712 facts / 192 CSVs / 14,779 municipal
observations (2,477 in 2024) / 300 districts / 44,154 blank DEF**, and loaded all
54,872,712 facts into PostGIS. DB read-back confirmed the previously recorded
per-year fact counts and 32 states in every year; totals were 300 districts and
44,154 blank DEF values.

Both runs resolved to generation
`4218953fe334ffd9a19ef61a4d054446d2d7e5f8314cbd2c73f21de54a9756ba`. The
successful second run reused the existing immutable generation (there is one
published generation directory); the atomic pointer therefore retains the same
generation ID and manifest hash. Verified final `current.json` SHA-256:
`2db10c444e93d02bb62e0d980cdec38fa5729b43d4f80a9405155f1a470dd6e4`;
manifest SHA-256: `624e81cc70c81207b5646e4956846fc0e6f6b6396dabca820d230a398bcd7795`.
The pointer hash is deterministic from the unchanged generation ID and manifest
hash; the second run confirmed staged artifact hashes matched the existing
generation before republishing the pointer. Computed ZIP hashes recorded in the
generation manifest:

| Year | ZIP SHA-256 |
|---:|---|
| 2009 | `e626e9528a91206c23fc8f96987e1a297db285e7cbc0fa1e37a18ed473ebf61c` |
| 2012 | `5999f86e21154138b904723cb5d55ebde9e108ac72872f2ff5695d9eb8fde9cd` |
| 2015 | `7435ac54a3a6aebf5d9c9466a064b320b64bf5ff8b4d8ae787bad898497341da` |
| 2018 | `b20981a0aea1ac773e7bc0b54784bba7619346585ba3996744ad22458279dd8b` |
| 2021 | `29bdfaaa33be5151c2ae8c8e406d8a27976006d11e6cbe201ac05cc04def4849` |
| 2024 | `c0de34d04e782ad99579b83591a6e3e6c8d1e20f4914d4845743bd79d2bd28b2` |

All eight output artifact SHA-256 values matched their manifest entries:

| Artifact | SHA-256 |
|---|---|
| `ccpc-section-2009.parquet` | `8cfb18527fc7a9f56c65a7d3c341c3ca685c737016041f8258e0fdf845956bd4` |
| `ccpc-section-2012.parquet` | `2cb8f30d826a573898bbef7c81b1eaa96cef85634fa925886a0257aa61c58e87` |
| `ccpc-section-2015.parquet` | `f5a9d5806a2a995505583b1235a70b48a515b0d33a8f4f1c6da0679192d0697a` |
| `ccpc-section-2018.parquet` | `1ec40612609f84146b8579ab496697a8d382114feb2bac5b7ee5cec0d0a3fd3d` |
| `ccpc-section-2021.parquet` | `74eb4d0b432d2db772ac4a51355bb8662acee789a3a265a0b37eb03cf29840f8` |
| `ccpc-section-2024.parquet` | `2fed51f8e8b24d751b269b87a42ffe765bfdeeb2b890ff70bb2c49cfbff14af4` |
| `municipal-observations.csv` | `bef9d79e6d24eba3da2c7beb01342500c0da23016a9acbc66db8787935aee472` |
| `municipal-observations.parquet` | `86f07c46054493205ec9ca83a350e7518169529203c49794d9e270dcd03ae84f` |

### Full-suite status

`sg docker -c 'docker compose run --rm --no-deps api python -m pytest -q'` →
**142 passed, 21 failed, 82 errors** (39.99s). The remaining suite failures are
outside this fix round: MVP/Jalisco raw and processed/model artifacts are absent
(including the Jalisco source CSVs, legacy municipal Parquet/provenance, and
prediction/model manifests), and GeoServer does not publish the `municipalities`
layer. These gaps account for official-data, export/delivery, and GeoServer
failures and cascading contract/integration/report API errors. Focused national
ingestion and migration checks pass independently.
