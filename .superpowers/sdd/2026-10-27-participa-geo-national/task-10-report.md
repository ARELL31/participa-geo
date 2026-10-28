# Task 10 — National reports and exports

**Status:** Implemented; delivery artifact complete. Existing legacy-scope integration checks remain blocked as detailed below.

## Delivered

- National methodology and executive PDFs use persisted national model/cohort evidence; national source provenance is included in report metadata.
- Report requests now carry level, state, district-plan, and observed-year metadata. Added state-scoped CSV/XLSX history, model-evidence exports, observed-2024 state/municipality and district fiches, and state-scoped GeoJSON using real GeoServer geometries.
- District fiche/GeoJSON values are observed 2024 under DERFE2023, include reconstruction coverage, and do not contain district predictions, uncertainty bands, or scenarios.
- National technical ZIP allowlisting and verification include national data/model artifacts, continuity evidence, district observations, source attributions, and reports. Raw source redistribution requires the explicit confirmation flag.
- Updated the report UI, generated API types/OpenAPI, delivery docs, and national delivery fixture expectations.

## Verification evidence

- National reporting contract: `7 passed`.
- Updated clean-room and scenario ZIP contract tests: `2 passed`.
- Full `tests/integration/test_delivery.py`: `6 passed, 1 failed`; the remaining scenario delivery integration test requires the absent legacy artifact `data/processed/gis/reference-2025-12-15.geojson`. No geometry was fabricated.
- Web checks via Docker `web-test`: typecheck, ESLint, Vitest (`10 files, 67 tests passed`), and production build passed. Vite reports the existing MapLibre bundle chunk-size advisory (>500 kB).
- Ruff check on changed Python files and `git diff --check` passed.
- Live API/GeoServer check: district GeoJSON for state 14 returned 20 geometries, each with observed-2024 coverage; no prediction fields were present. District and state observed fiche requests both returned ready PDFs. District fiche content is also covered by the PDF text contract test.
- National delivery regenerated from real artifacts with confirmed source redistribution: `dist/task10/technical.zip`, 460,295,090 bytes; verified complete (`309` package members checked), no scenario required. SHA-256: `4e74898cb8035bb1fbab46f596dbb7ae13be1999221903266df9ecad753a44e2`.

## Concerns / known suite incompatibilities

- The legacy `tests/integration/test_report_api.py::test_scenario_csv_matches_persisted_api` expects a 125-row Jalisco scenario; the current persisted national model correctly exports its 2,477-municipality cohort. The test expectation/scope has not been changed here.
- The broader `tests/unit/test_exports.py` still assumes the previous Jalisco-only model artifacts and metrics, including the absent `data/processed/model/predictions-2027.parquet`; it is not a Task 10 regression signal for the national artifacts.
- The full delivery scenario integration test depends on the missing legacy Jalisco reference geometry noted above. Task 10 national exports were separately exercised against the live national GeoServer/API.
- The task report lives under `.superpowers/sdd/`, which is ignored by the repository configuration; it is available in the worktree but is not included in the source commit.

## Commit

Source commit: `feat: generate national reports and reproducible exports`.

## Fix round 1

**Status:** Review findings fixed; national delivery regenerated and independently verified.

- National/state history CSV and XLSX now export per-municipality observations, with state filters returning the state's municipalities; district history exports only observed 2024 DERFE2023 rows. The aggregate history API is unchanged.
- National model evidence carries `state_code` and `state_name` on feature, exclusion, and selected-contribution rows. Candidate-M1 per-municipality contributions are explicitly omitted from the national evidence file; features, exclusions, and selected contributions remain. Exports over 20,000 rows fail with a clear API validation error rather than truncating.
- Delivery source metadata now includes INE MGS attribution, cut, URL, and validated SHA-256 for each of 32 state archives. `sources/SOURCES.md`, `sources/sources.json`, `MANIFEST.json`, and the methodology PDF carry the geography provenance.
- State aggregate fiches now use the catalogued state name and the label “Entidad”; municipality and district fiches use their appropriate labels.
- Updated the scenario CSV contract to check the persisted national cohort size rather than the legacy Jalisco-only 125 rows. Two geometry-dependent legacy integrations skip only when their required MVP `reference-2025-12-15.geojson` is absent; no geometry was fabricated.

### Fix-round verification

- Focused reporting/delivery/API tests: `32 passed, 2 skipped` (the two scoped missing-reference-geometry skips); one existing Starlette/httpx deprecation warning.
- Web checks: typecheck passed; ESLint passed; Vitest `10 files, 67 tests passed` (run serially after an initial parallel run showed a transient MSW race); production build passed with the existing MapLibre >500 kB chunk advisory.
- Ruff check on changed Python/tests and `git diff --check`: passed.
- National `deliver --skip-sources` regenerated `dist/task10-fix-round-1/technical.zip`; separate `verify-delivery` returned `complete: true`, 271 package members. ZIP SHA-256: `8612e93268ca260ed1b85e2ef210328d6c1d0ed4666ae15556d6af19ea9d1d86` (2,349,846 bytes). Verified the ZIP sources document and manifest each contain all 32 MGS entries; the methodology PDF contains every MGS URL and full checksum. Checksum inventory remains usable when raw archives are absent; local archive bytes are validated when present.

### Remaining limitation

- `tests/integration/test_report_api.py::test_scenario_geojson_has_125_4326_reference_geometries` and `tests/integration/test_delivery.py::test_cli_delivery_builds_verified_package_with_real_scenario` remain skipped only when the legacy MVP GeoJSON is absent. National report/delivery behavior is covered and verified independently.
