# Task 7 report — API nacional por nivel y gateway GIS

**Status: IMPLEMENTED.** District predictions and scenarios remain explicitly unavailable; district history and summaries expose observed 2024 data only.

## Implemented

- Added level-aware territory, history, model, prediction, scenario, and recommendation APIs. The default remains state 14; `state_code=all` enables national queries, and list pages support up to 500 records.
- Added national participation summaries for municipality and federal-district levels, using summed counts and reporting level-specific coverage/insufficient data.
- Added observed district history/summaries for 2024. District prediction and scenario requests return `409 district_model_unavailable`; no district predictions are fabricated.
- Added the national model loader and municipal-year observation loading, migration-backed read-only API catalogue views, and scenario bounds (1,000 territories; 128 KiB request body).
- Added bounded, read-only GIS gateway behavior and updated API contracts, generated OpenAPI, and TypeScript API types.
- Added regression coverage for national model loading, API behavior, scenario rejection/limits, and GIS filtering/bounds.

## Acceptance data

Previously verified against the populated national database/API:

- 2,477 municipal references and predictions; 854 insufficient predictions have null estimates.
- 300 observed 2024 districts.
- 32 municipal and 32 district summary rows; summary count totals match their corresponding history totals.
- `model load-national` loaded model run `0e288804-1c44-523e-a4a3-7a7db70e8c77` idempotently.

## Verification

- Ruff on all Task 7 changed Python source/tests: **passed** (`All checks passed`).
- Isolated national model-loader and GIS unit tests: **20 passed**.
- Focused test command in this checkout: **25 passed, 24 errors**. The passing tests include the isolated unit/model/GIS coverage; DB-backed contract tests could not initialize because test configuration points to hostname `db`, which does not resolve in this mounted environment. This is an environment limitation, not a passing contract-suite result.
- The repository `.venv` launchers reference missing `/workspace/.venv/bin/python`; `uv` is unavailable. Tests were run using system Python with the existing venv site-packages added to `PYTHONPATH`.
- Web typecheck could not run in the mounted test container because `node` and `vite/client` type definitions were unavailable.
- The broader unit suite has pre-existing missing Jalisco model artifact failures under `/workspace/data/processed/model/*` (recorded during earlier verification); these remain outside Task 7.

## Scope decisions and limitations

- District history is limited to observed 2024 and aggregates existing municipality×district intersections. No predictive district model or scenario behavior is exposed.
- National model loading includes the 14,779 municipal-year aggregate observations needed for history and summaries.
- The national model bundle lacks `risk_unstable`; the loader defaults this field to `false`.
- Latest-version selection is qualified by both year and state because dataset versions are state-scoped; this prevents partial national totals.

## Fix round 1 — Task 7 review findings

- Added explicit `level` filtering to `/recommendations` and `/models` (including model detail). District model/recommendation requests now return 409 `district_model_unavailable`; invalid and repeated/mixed `level` values return 422. Recommendations also pass `level` and `state_code` through to the prediction query.
- Restricted model listing/details and prediction/recommendation model selection to the latest municipal model with the full 2,477-territory, 32-state prediction set. Other/legacy runs are hidden from `/models` and return 404 when requested for predictions or recommendations. The DB contract regression inserts a legacy run and verifies it is inaccessible.
- Fixed test DB teardown ordering by dropping the migration-created partitioned facts and geography tables before `Base.metadata.drop_all`. Reworked the contract fixture to seed from national aggregate/model artifacts, retaining the state-14 data assertions while removing dependencies on absent Jalisco-only files.
- Fixed deterministic national scenario result ordering and persisted scenario reconstruction, preserving the GET-after-POST equality contract across duplicate municipal codes in different states.
- Updated OpenAPI, generated TypeScript types, API contract text, and TypeScript fixtures for required level fields.

Verification for this fix round:

- `sg docker -c 'docker compose run --rm --no-deps api python -m pytest tests/contract/test_read_api.py tests/contract/test_scenario_api.py -q'`: **34 passed** (one existing Starlette/httpx deprecation warning).
- Ruff on changed API/test Python files: **passed** (`All checks passed`).
- Web TypeScript check in the pinned Node 24 Docker deps image: **passed** (`npm run typecheck`).
