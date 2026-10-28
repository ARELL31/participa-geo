# Task 9 Report: District Profiles and Municipality–District Intersections

## Outcome

Implemented district profiles with the 2023 plan and observed 2024 abstention, including coverage/insufficiency indicators, district reference maps, and constituent municipality listings. Municipality profiles now show every intersecting district through an aggregate N:M crosswalk; split municipalities remain represented as multiple intersections, with no dominant-district assignment. No district 2027 predictions or scenario controls were added.

The crosswalk is exposed through the read-only `GET /territories/{territory_id}/municipal-districts` endpoint. District geometry is requested through the existing state-bounded WFS gateway.

## Changes

- Added district list/profile/map UI and selected-state navigation.
- Added municipality intersection panel with aggregate counts, shares, and coverage.
- Added the read-only API route, schema, repository query, and OpenAPI snapshot.
- Added UI/API contract tests and a real-stack Playwright test.

## Verification

- Typecheck: passed (previous run during implementation).
- Lint: passed (previous run during implementation).
- Production build: passed (previous run during implementation; existing Vite chunk-size warning noted).
- Focused territory tests and individual OpenAPI/crosswalk API tests: passed (previous runs during implementation).
- Full Vitest run: 62 passed, 3 failed while running in parallel. Failures were a NationalPanel loading-state timeout, a PredictionPage table lookup failure, and a ScenarioPage timeout. Their cause was not confirmed.
- Serial rerun: not possible in this continuation because Node/npm are unavailable in the host environment and Docker access to `/var/run/docker.sock` is denied.
- Full API contract suite: previously exceeded the 120-second command timeout; individual relevant tests passed.
- Real-stack Playwright and live database route verification: not completed in this environment.

## Outstanding Concern

Re-run the failed Vitest cases serially and complete the API contract and Playwright checks in an environment with the project’s Docker stack available before treating the full validation matrix as green.
