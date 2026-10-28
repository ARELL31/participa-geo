# Task 5 report — Modelo municipal nacional

**Status: IMPLEMENTED; real national release BLOCKED by missing national identity/coverage rows in PostGIS.**

## Implemented

- Added state-qualified national municipal cohorts and M0/M1 temporal training in
  `apps/api/participa_geo/prediction/national.py`.
- M1 uses the six specified predictors plus 31 state one-hot fixed effects
  (reference state 01), `StandardScaler` fit on the training rows only, and
  `Ridge(alpha=1.0)`. Candidate comparison is on 2021, strict MAE improvement is
  required to select M1, and 2024 does not alter selection.
- Added strict national aggregate and identity readers in
  `pipelines/training/national.py`. The identity reader requires all 2,477
  municipalities in 32 states with at least one coherent status correspondence each;
  absent evidence raises an error rather than assuming identity/coverage.
- Registered `train-national-municipal`; outputs target the specified model
  artifact directory. JSON, Parquet and CSV only; no pickle/joblib.
- Added methodology and five unit tests covering explicit identity, state/code
  collision avoidance, quality exclusions/nulls, fixed effects, the prediction
  universe, district rejection, and frozen 2024 selection/model identity.
- Did not implement district prediction/modeling, scenarios, API, UI or reports.

## Real national run and metrics

The national aggregate generation is readable and reports **54,872,712 section
facts, 14,779 municipal observations and 2,477 municipalities**. The attempted
command was:

```text
python -m participa_geo.cli train-national-municipal
```

It failed loudly at `read_national_identity_statuses()` with
`IncompleteIdentityError: national municipality identity/coverage records are
missing`. A read-only database inspection confirmed `territory_version` has
zero rows and `territory_correspondence` has zero rows. The local database is
therefore empty for cartographic reference identities/statuses; national
cartography and continuity aggregates do not supply a separate identity-status
artifact. In accordance with the requirement not to assume verification or
silently drop territories, **no national model artifacts were produced**. Thus
M0/M1 national MAE, P90 band, and empirical 2024 coverage are unavailable—not
zero and not estimated. Populate the national reference/correspondence identity
records from the verified cartography workflow, then rerun the command to
complete acceptance and record metrics.

## Verification

- TDD RED: the new focused test initially failed collection because
  `prediction.national` did not exist.
- TDD GREEN: `tests/unit/national/test_national_model.py`: **5 passed**.
- Task 1–4 focused regression set (`tests/unit/national`, national GIS CLI, and
  `tests/integration/national`): **62 passed**, including the 2024-freeze
  assertion.
- Ruff on all changed Python source/tests: **passed**.
- Full suite: **178 passed, 19 failed, 82 errors**. Gaps are environment/baseline
  prerequisites: MVP Jalisco files/artifacts absent under `data/processed` and
  `data/raw/ccpc`; the currently running PostGIS database is empty/uninitialized
  for the Jalisco baseline (contract/integration tests); and the existing
  GeoServer WFS returned zero Jalisco features. These failures are unrelated to
  the new municipal model; national identity absence is separately the real-run
  blocker above.

## Known limits

- No actual national evaluation or 2,477-row artifact can be claimed until the
  identity/correspondence records exist and the real CLI completes.
- `footprint_status=not_verified` is allowed as explicitly unverified; missing
  status data is not.
- The district product remains observed 2024 only, as required by the scope
  decision.

## Fix round 1 — MGS municipal identity prerequisite and real training

The blocked status above is superseded by this round. Added an idempotent
national municipal identity builder in
`pipelines/validation/identity_national.py`, called by
`train-national-municipal` before identity/cohort loading. It reads only the
Task 4 `geo_municipality` MGS layer, requires exactly 2,477 unique valid
state+municipality codes across all 32 states, and writes deterministic
2025-12-15 reference territories with EPSG:4326 geometry, source SRID and
provenance. For each observed municipality-year it writes an origin and an
evidence-bearing correspondence; the identity lookup uses entity+code, never
name or the district bridge. Unmatched origins can be explicitly represented
as ambiguous with a null reference ID (migration `0012`); identity is marked
`verified_catalogue` only for a matching MGS reference and `not_verified`
footprint is retained explicitly. The MGS reference check fails closed for
missing, duplicate, invalid, or non-4326 keys/geometries.

The Task 4 MGS source and national CCPC aggregate were already imported in
PostGIS for this run. First and repeat execution of
`sg docker -c 'docker compose run --rm --no-deps api python -m participa_geo.cli train-national-municipal'`
both completed with the same `model_run_id`:
`dc24b18b-406b-597c-9003-5ff900cb09a0` (family M0; 1,623 eligible candidates;
2,477 prediction records). Persisted counts after repeat execution:

- MGS reference territories: **2,477**; all prediction rows have
  `verified_catalogue` and `not_verified`.
- Observed-year origin/correspondence rows: **14,779 / 14,779**; ambiguous
  correspondences: **0**.
- Origin observations by year: 2009 **2,458**; 2012 **2,455**; 2015 **2,458**;
  2018 **2,463**; 2021 **2,468**; 2024 **2,477**. The absent 22 municipalities
  in 2012 remain absent; no historical origins were fabricated.
- Prediction statuses: **1,623 eligible** and **854 insufficient** (all 854
  have null estimates), covering all 2,477 reference municipalities.

Actual evaluation from `data/processed/national/model/evaluation.json`:

| Family | 2021 MAE (selection) | 2021 RMSE | 2021 bias | 2021 weighted MAE | 2024 MAE | 2024 RMSE | 2024 bias | 2024 weighted MAE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| M0 (selected) | 12.1854 pp | 16.0098 pp | 8.2731 pp | 8.0470 pp | 5.5602 pp | 7.1251 pp | -4.3122 pp | 3.5371 pp |
| M1 | 12.3743 pp | 15.5636 pp | 3.5394 pp | 7.7989 pp | 8.7546 pp | 10.3805 pp | -8.1489 pp | 5.2171 pp |

Selection used 2021 MAE only, so M0 was selected; the 2024 holdout was not used
for family selection. The selected-family P90 absolute-error band is **28.8979
pp** based on 1,338 eligible 2021 errors. Empirical 2024 coverage is **1,317 /
1,319 = 99.8484%** within that band. Artifacts written: `manifest.json`,
`model.json`, `evaluation.json`, `exclusions-by-cut.csv`, and
`predictions-2027.parquet` under `data/processed/national/model/`.

Verification commands/results:

- `sg docker -c 'docker compose run --rm --no-deps api python -m pytest tests/unit/national tests/integration/national -q'` initially: **64 passed, 1 failed** because the migration-chain regression still expected Alembic head `0011`. Updated that assertion for the new migration `0012`.
- `sg docker -c 'docker compose run --rm --no-deps api python -m ruff check apps/api/participa_geo/db/models.py pipelines/validation/identity_national.py pipelines/training/national.py tests/unit/national/test_national_identity_builder.py tests/unit/national/test_national_model.py alembic/versions/0012_unmatched_identity_correspondence.py'`: **All checks passed**.
- Identity builder tests cover idempotency, 2,477 references, entity-qualified code matching independent of name, ambiguous unmatched origin, missing 2012 observations, and duplicate-key fail-closed behavior. Training tests verify the identity builder runs before model training and returned statuses feed predictions.

Known caveat: all 14,779 observed origins in the current national aggregate
matched the MGS catalogue, so the actual run produced zero ambiguous
correspondences. Historical source gaps remain represented as absent origin
rows rather than inferred identities.

The final full-suite run was `sg docker -c 'docker compose run --rm --no-deps
api python -m pytest -q'`: **183 passed, 19 failed, 82 errors**. The focused
national suite above passes. Failures/errors are unrelated Task 5 behavior and
cluster around missing Jalisco MVP inputs/artifacts (`data/raw/ccpc`,
`data/processed/model`, and `data/processed/municipal-observations.parquet`),
uninitialized Jalisco fixture/database state for legacy contract/integration
tests, and the shared GeoServer now serving the imported national layer (2,477
features where the legacy Jalisco-only test expects 125). No Task 1–4
application source behavior was changed beyond making the migration-chain test
expect the new Alembic head `0012`; the national import/runtime environment
does make that legacy 125-feature integration assumption no longer match the
loaded GeoServer data.

## Fix round 1 — review follow-up

Included the 2021-validation M1 candidate fit (trained on the 2015 and 2018
cohorts) and its 2021 M1 evaluation metrics explicitly in the canonical payload
passed to `compute_model_run_id`. The persisted `model.json` records the same
candidate fit and metrics. A regression test captures that canonical payload,
changes one 2021-fit coefficient, and verifies the computed model run ID
changes. The test also verifies the hashed 2021 candidate metrics match the
persisted 2021 M1 evaluation. The 2024 validation candidate fit/evaluation is
also explicit in the canonical payload.

Added `evaluation.json.state_metrics` for all represented states, both M0/M1
families, and 2021/2024 evaluation cuts. Each state entry reports unweighted
MAE, RMSE, bias (prediction minus actual), and sample count `n`. All 32 states
have entries for both evaluation years and both families in the real run. For
example, selected M0 State 01 has 2021 MAE/RMSE/bias **20.0855/21.1441/20.0855
pp** (`n=11`) and 2024 **3.7770/6.0286/3.7364 pp** (`n=10`). Complete metrics
are in `data/processed/national/model/evaluation.json`.

Real retraining, twice, completed with stable updated
`model_run_id=0e288804-1c44-523e-a4a3-7a7db70e8c77`, family M0, 1,623 eligible
candidates, and 2,477 prediction records. Model metrics and coverage are
unchanged from the prior fix: M0 2021/2024 MAE **12.1854/5.5602 pp**, M1
**12.3743/8.7546 pp**; selected P90 band **28.8979 pp** and 2024 empirical
coverage **1,317/1,319 (99.8484%)**. Verified the model/manifest/prediction run
IDs agree, the 2021 M1 metrics match between model and evaluation artifacts,
and all four manifest-listed artifact SHA-256 hashes match their files.

Verification:

- TDD RED: `tests/unit/national/test_national_model.py` initially failed on
  missing `state_metrics` and `candidate_m1_2021` in the hashed input.
- TDD GREEN/focused: `sg docker -c 'docker compose run --rm --no-deps api
  python -m pytest tests/unit/national tests/integration/national -q'` —
  **66 passed**.
- Ruff on the modified model and unit tests — **All checks passed**.
- Real command, twice:
  `sg docker -c 'docker compose run --rm --no-deps api python -m participa_geo.cli train-national-municipal'`
  — both returned model run ID `0e288804-1c44-523e-a4a3-7a7db70e8c77`.
- Full suite: **184 passed, 19 failed, 82 errors**. Failures/errors remain
  attributable to missing Jalisco MVP raw/processed files and Jalisco test DB
  fixtures; the GeoServer test expects 125 Jalisco features while the shared
  service contains 2,477 imported national municipality features. These do
  not involve the changed national run identity or state-level metrics.
