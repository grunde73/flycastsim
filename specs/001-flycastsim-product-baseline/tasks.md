# Tasks: flycastsim Product Baseline

> **NON-EXECUTABLE REFERENCE ONLY — DO NOT IMPLEMENT THESE TASKS.**
> This reconstruction checklist was generated to start using Spec Kit and
> describe a hypothetical clean-room rebuild. It is not approved work, does
> not authorize changes to application code, and must not be passed to
> `/speckit-implement`. Use the baseline documents only as context for future,
> separately scoped feature specifications.

**Input**: Design documents from `specs/001-flycastsim-product-baseline/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/`

**Tests**: Tests are included because the product specification makes the six
FEM verification cases, regression behavior, safe archive handling, and
independent user-journey checks acceptance requirements.

**Organization**: Tasks are grouped by the six user stories in `spec.md`.
They describe a hypothetical clean-room reconstruction and are retained for
workflow reference only; do not execute them.

## Phase 1: Setup

**Purpose**: Establish the Python project and its repeatable development
environment.

- [ ] T001 Create `pyproject.toml` with Python >=3.12, Hatchling packaging,
  runtime dependencies, optional docs dependencies, default app/dev groups,
  pytest configuration, and Ruff configuration as listed in `plan.md`.
- [ ] T002 [P] Create the `src/flycastsim/` package skeleton with
  `src/flycastsim/__init__.py`, `src/flycastsim/sho/__init__.py`,
  `src/flycastsim/fem/__init__.py`, and `src/flycastsim/rod/__init__.py`.
- [ ] T003 [P] Create the repository test and documentation directory
  skeletons at `tests/unit/`, `docs/`, and `examples/`, with minimal valid
  entry files at `docs/index.rst` and `examples/rod_profile_fit.py`.
- [ ] T004 Generate and commit the reproducible dependency lock at `uv.lock`
  from `pyproject.toml`; verify `uv sync --all-extras` succeeds.

## Phase 2: Foundational

**Purpose**: Build shared package, error, data, and UI foundations required by
the user stories.

- [ ] T005 Implement shared input-validation helpers in
  `src/flycastsim/_validation.py` for finite numeric values, physical
  quantities, and informative value errors used by model and data loaders.
- [ ] T006 [P] Implement package-resource path helpers in
  `src/flycastsim/_resources.py` so bundled JSON/CSV data loads from an
  installed wheel without depending on the working directory.
- [ ] T007 [P] Create the shared Streamlit entry and section navigation in
  `streamlit_app.py` for the simple model, Cast #1, and Rod parameters views.
- [ ] T008 Create project-level CI in `.github/workflows/ci.yml` to install
  Python 3.12 and `uv`, sync all extras, and run pytest on pull requests and
  pushes to `main`.
- [ ] T009 [P] Configure the Sphinx HTML documentation build in
  `docs/conf.py` and `docs/Makefile`, with API generation from
  `src/flycastsim/`.

**Checkpoint**: Package, test, documentation, and application entry points
exist; user-story work can proceed.

## Phase 3: User Story 1 - Explore the simple casting model (Priority: P1)

**Goal**: Let users tune the brick-spring-car model and inspect results against
the reference response.

**Independent Test**: Run `tests/unit/test_simple_brick_spring.py` and launch
the simple-model view; verify its defaults, selectable results, reference
comparison, event markers, animation, and invalid stop/turn time warning.

### Tests for User Story 1

- [ ] T010 [P] [US1] Create oscillator numerical and boundary tests in
  `tests/unit/test_simple_brick_spring.py` for default outputs, changed
  parameters, and turn/stop time behavior.
- [ ] T011 [P] [US1] Create Plotly result and animation contract tests in
  `tests/unit/test_simple_brick_spring_helpers.py` for selectable output
  columns, reference series, event markers, and animation frames.

### Implementation for User Story 1

- [ ] T012 [P] [US1] Implement the forced oscillator state equations and
  tabular simulation result in `src/flycastsim/sho/model.py`.
- [ ] T013 [P] [US1] Implement result plotting and client-side animation in
  `src/flycastsim/sho/helpers.py`.
- [ ] T014 [US1] Export `simple_sim`, the model helpers, plotting helpers, and
  animation helpers from `src/flycastsim/sho/__init__.py` and
  `src/flycastsim/__init__.py`.
- [ ] T015 [US1] Implement the simple-model controls, reference comparison,
  column selection, event warnings, plots, and animation in `streamlit_app.py`.
- [ ] T016 [US1] Document the 1-D model's equations, assumptions, controls, and
  example usage in `docs/brick_spring.rst`.

**Checkpoint**: The first independently demonstrable MVP story works without
requiring the FEM or rod workflows.

## Phase 4: User Story 2 - Run the reference cast (Priority: P1)

**Goal**: Reproduce the coupled rod/line/leader continuum simulation and
provide the Cast #1 visual comparison.

**Independent Test**: Run all six exact cases and convergence tests in
`tests/unit/test_fem_verification.py`; run Cast #1 tests in
`tests/unit/test_fem_cast.py` and `tests/unit/test_fem_multidomain.py`; launch
the app and verify explicit run behavior and the measured chord/event output.

### Tests for User Story 2

- [ ] T017 [P] [US2] Create the six analytic/static/dynamic verification
  cases and second-order spatial convergence assertions in
  `tests/unit/test_fem_verification.py`.
- [ ] T018 [P] [US2] Create FEM domain, boundary-condition, and nonlinear
  solver tests in `tests/unit/test_fem_solver.py`.
- [ ] T019 [P] [US2] Create drag-law behavior tests in
  `tests/unit/test_fem_drag.py` for zero drag and supported Reynolds regimes.
- [ ] T020 [P] [US2] Create multi-domain junction and coupled static/dynamic
  tests in `tests/unit/test_fem_multidomain.py`.
- [ ] T021 [P] [US2] Create Cast #1 stroke, simulation, chord, speed, and
  explicit-run/display-only behavior tests in
  `tests/unit/test_fem_cast.py`.
- [ ] T022 [P] [US2] Create coordinate reconstruction and derived-quantity
  tests in `tests/unit/test_coords.py`.

### Implementation for User Story 2

- [ ] T023 [P] [US2] Implement the `Subdomain` model and uniform/chain domain
  construction in `src/flycastsim/fem/domain.py`.
- [ ] T024 [P] [US2] Implement node-major seven-field packing, named field
  indices, and safe field access in `src/flycastsim/fem/state.py`.
- [ ] T025 [US2] Implement staggered spatial residual operators, boundary
  conditions, and pinned/welded junction residuals in
  `src/flycastsim/fem/operators.py`.
- [ ] T026 [US2] Implement Newton iteration, sparse two-colour Jacobian
  assembly, sparse solve, static solves, and multi-domain solves in
  `src/flycastsim/fem/solver.py`.
- [ ] T027 [US2] Implement generalised-alpha time integration with Newton
  updates, Jacobian reuse, and convergence handling in
  `src/flycastsim/fem/genalpha.py`.
- [ ] T028 [P] [US2] Implement Reynolds-number air drag and the documented
  force decomposition in `src/flycastsim/fem/drag.py`.
- [ ] T029 [P] [US2] Implement physical-position reconstruction, speed,
  tension, line-tip indexing, and rigid-lever diagnostics in
  `src/flycastsim/fem/coords.py`.
- [ ] T030 [US2] Implement component JSON/CSV loading, AFTM line-mass scaling,
  and packaged rig loading in `src/flycastsim/fem/components.py`.
- [ ] T031 [US2] Implement ordered subdomain assembly, global node offsets,
  and pinned/welded coupling in `src/flycastsim/fem/multidomain.py`.
- [ ] T032 [US2] Implement casting-stroke input, sample cast construction,
  Cast #1 configuration, simulation entry points, and chord/tip diagnostics
  in `src/flycastsim/fem/cast.py`.
- [ ] T033 [P] [US2] Implement cast snapshots, animation, chord comparison,
  tip deflection, and speed plots in `src/flycastsim/fem_helpers.py`.
- [ ] T034 [US2] Implement Cast #1 controls, rod/line selectors, explicit
  simulation launch, source-fingerprinted caching, and result views in
  `streamlit_app.py`.
- [ ] T035 [US2] Document FEM equations, verification cases, deliberate
  deviations, and current model coverage in `docs/fem.rst`.

**Checkpoint**: The six exact verification cases pass before Cast #1 is
accepted; Cast #1 remains a qualitative reference comparison.

## Phase 5: User Story 3 - Estimate rod swingweight (Priority: P1)

**Goal**: Calculate butt-axis moment of inertia from section measurements and
show per-section contributions.

**Independent Test**: Run `tests/unit/test_rod_swingweight.py` against the
published worked examples and verify the app supports both example presets and
custom measurements.

### Tests for User Story 3

- [ ] T036 [P] [US3] Create swingweight formula, ferrule-overlap, reel-seat
  correction, units, and invalid balance-point tests in
  `tests/unit/test_rod_swingweight.py`.

### Implementation for User Story 3

- [ ] T037 [P] [US3] Implement `RodSection`, section MOI, ferrule overlap,
  reel-seat/grip correction, and result dataclasses in
  `src/flycastsim/rod/swingweight.py`.
- [ ] T038 [P] [US3] Implement worked-example rod records and their package
  loader in `src/flycastsim/rod/data.py`.
- [ ] T039 [P] [US3] Implement the swingweight contribution chart in
  `src/flycastsim/rod/helpers.py`.
- [ ] T040 [US3] Export swingweight types/functions and worked-example loaders
  from `src/flycastsim/rod/__init__.py` and `src/flycastsim/__init__.py`.
- [ ] T041 [US3] Implement the Swingweight app view with example selection,
  custom section table, finished-rod toggle, result, and contribution chart
  in `streamlit_app.py`.
- [ ] T042 [US3] Document measurement procedure, assumptions, units, and
  worked examples in `docs/rod.rst`.

**Checkpoint**: Swingweight works from Python and the app, independently of
image-based profile fitting.

## Phase 6: User Story 4 - Fit and compare a measured rod (Priority: P1)

**Goal**: Accept rod measurement data, trace and fit a profile, present fit
diagnostics, and make the fitted rod downloadable and session-usable.

**Independent Test**: Run the rod archive, elastica, imaging, vibration,
measurement, and profile-fit tests; use a bundled measurement set to verify
trace preview, a completed quick fit, exported files, and session selection.

### Tests for User Story 4

- [ ] T043 [P] [US4] Create archive validation, safe extraction, and fitted-rod
  zip tests in `tests/unit/test_rod_archive.py`.
- [ ] T044 [P] [US4] Create static elastica solver tests in
  `tests/unit/test_rod_elastica.py`.
- [ ] T045 [P] [US4] Create image tracing, calibration, and trace edge-case
  tests in `tests/unit/test_rod_imaging.py`.
- [ ] T046 [P] [US4] Create vibration eigenfrequency and convergence tests in
  `tests/unit/test_rod_vibration.py`.
- [ ] T047 [P] [US4] Create measurement schema, relative paths, optional data,
  fit/export, and absolute-scale validation tests in
  `tests/unit/test_rod_measurement.py`.
- [ ] T048 [P] [US4] Create parametrization, joint-fit, constraint, and
  synthetic-profile recovery tests in `tests/unit/test_rod_profile_fit.py`.

### Implementation for User Story 4

- [ ] T049 [P] [US4] Implement static large-deflection cantilever solvers and
  load-sequence continuation in `src/flycastsim/rod/elastica.py`.
- [ ] T050 [P] [US4] Implement tip-mass bending-frequency calculations in
  `src/flycastsim/rod/vibration.py`.
- [ ] T051 [P] [US4] Implement image calibration, rod centre-line tracing,
  tip detection, and trace result types in `src/flycastsim/rod/imaging.py`.
- [ ] T052 [US4] Implement monotone log-EI and mass-density parameterizations,
  fit residuals, constraints, and joint profile optimization in
  `src/flycastsim/rod/profile_fit.py`.
- [ ] T053 [US4] Implement `rod.yaml` schema loading, guided measurement
  creation, fit presets, progress callbacks, and fitted-profile export in
  `src/flycastsim/rod/measurement.py`.
- [ ] T054 [US4] Implement fitted-rod loading, profile evaluation, component
  conversion, packaged-rod loading, and fit-summary parsing in
  `src/flycastsim/rod/fitted.py`.
- [ ] T055 [US4] Implement safe measurement archive extraction and fitted-rod
  archive creation in `src/flycastsim/rod/archive.py`.
- [ ] T056 [P] [US4] Implement fitted profile, bend, frequency, load, and
  trace-overlay plots in `src/flycastsim/rod/helpers.py`.
- [ ] T057 [US4] Implement profile comparison, zip upload, guided form,
  click-to-place image calibration, trace preview, fitting progress,
  download, content-addressed shared cache, and session registration in
  `rod_profile_pages.py`.
- [ ] T058 [US4] Connect Swingweight, Stiffness profiles, and Upload & fit
  views through the Rod parameters navigation in `streamlit_app.py`.
- [ ] T059 [US4] Document measurement schema, fit method, bundled profiles,
  limitations, and app workflow in `docs/rod_profile.rst`.

**Checkpoint**: Users can reproduce a fit from a measurement set, inspect its
limitations, download the fitted rod, and select it in the current session.

## Phase 7: User Story 5 - Use the models programmatically (Priority: P2)

**Goal**: Provide the documented public Python API and package the component
and fitted-rod data for use without Streamlit.

**Independent Test**: Build a wheel, install it into a clean Python >=3.12
environment, and run documented examples for the oscillator, FEM cast,
swingweight, and fitted-rod loading.

### Tests for User Story 5

- [ ] T060 [P] [US5] Create public import, API alias, package-resource, and
  no-Streamlit-import tests in `tests/unit/test_public_api.py`.
- [ ] T061 [P] [US5] Create installed-wheel data availability tests in
  `tests/unit/test_packaged_data.py` for the Cast #1 rig, three fitted rods,
  and worked-example rods.

### Implementation for User Story 5

- [ ] T062 [P] [US5] Add Cast #1 rod/line/leader rig JSON and CSV profiles to
  `src/flycastsim/data/components/cast1/`.
- [ ] T063 [P] [US5] Add PA905, XP590, and TCR590 fitted-rod metadata, CSV
  profiles, and fit summaries to
  `src/flycastsim/data/components/fitted_rods/`.
- [ ] T064 [P] [US5] Add swingweight worked-example data to
  `src/flycastsim/data/rods/example_rods.json`.
- [ ] T065 [US5] Include packaged JSON/CSV data in source and wheel
  distributions through `MANIFEST.in` and `pyproject.toml`.
- [ ] T066 [US5] Finalize the documented import surface and compatibility
  aliases in `src/flycastsim/__init__.py`, `src/flycastsim/fem/__init__.py`,
  `src/flycastsim/rod/__init__.py`, and `src/flycastsim/sho/__init__.py`.
- [ ] T067 [US5] Add runnable examples for package usage and rod profile fitting
  in `flysim_examples.ipynb` and `examples/rod_profile_fit.py`.
- [ ] T068 [US5] Document installation, quickstart, public APIs, and packaged
  data usage in `README.md` and `docs/index.rst`.

**Checkpoint**: The built distribution contains usable library code and
bundled data, and examples run without importing the Streamlit app.

## Phase 8: User Story 6 - Access the hosted application (Priority: P2)

**Goal**: Preserve public Streamlit access, PR validation/preview behavior,
and publication after a merge into `main`.

**Independent Test**: Verify a pull request runs validation or a preview
without replacing the deployed public app; merge to `main` and verify the
updated public URL serves the app.

### Tests and implementation for User Story 6

- [ ] T069 [US6] Identify the current public app host, deployment integration,
  required repository/environment secrets, and PR-preview mechanism; record
  confirmed values and setup steps in `docs/deployment.rst`.
- [ ] T070 [US6] Configure pull-request validation or preview without
  publishing over production, and configure merge-to-main publication in
  `.github/workflows/app-deploy.yml` using the confirmed hosting integration.
- [ ] T071 [US6] Document public URL, deployment triggers, required external
  configuration, and failure/rollback procedure in `README.md` and
  `docs/deployment.rst`.
- [ ] T072 [US6] Add a deployment workflow validation check in
  `.github/workflows/ci.yml` or `tests/unit/test_deployment_config.py` to
  verify trigger scoping and prevent PR jobs from replacing production.

**Checkpoint**: PR work cannot replace the public app; merges into `main`
publish the updated application, and setup requirements are documented.

## Phase 9: Polish and Cross-Cutting Concerns

**Purpose**: Verify the complete reconstruction, documentation, packaging,
and project-wide quality gates.

- [ ] T073 [P] Update the physics theory-coverage and intentional-deviation
  mapping in `docs/fem.rst` to match the reconstructed numerical code.
- [ ] T074 [P] Verify all packaged component and fitted-rod data is included
  and repository-only measurement assets are excluded using
  `tests/unit/test_packaged_data.py` and the built distribution contents.
- [ ] T075 Run `uv run ruff check .` and resolve project lint failures in the
  relevant source/test files.
- [ ] T076 Run `uv run pytest` and resolve failures across
  `tests/unit/`.
- [ ] T077 Run `uv run --extra docs --directory docs make html` and resolve
  broken references or documentation build failures in `docs/`.
- [ ] T078 Execute every scenario in
  `specs/001-flycastsim-product-baseline/quickstart.md` and record any
  deviations in that file.

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No prerequisites; complete before foundation work.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories.
- **US1 / US2 / US3 / US4 (Phases 3–6)**: Depend on the shared package and app
  foundation. The numerical FEM (US2), oscillator (US1), swingweight (US3),
  and rod-fit internals (US4) can proceed in parallel after Phase 2, subject
  to shared-file coordination.
- **US5 (Phase 7)**: Depends on US1–US4 implementation because it packages and
  exposes their public APIs and bundled artifacts.
- **US6 (Phase 8)**: Depends on the app and its CI checks from US1, US2, and
  US4; can proceed independently of later packaging refinements.
- **Polish (Phase 9)**: Depends on all required user stories.

### User Story Dependencies

- **US1 (P1)**: Independent after Phase 2; MVP scope is this oscillator and its
  app view only.
- **US2 (P1)**: Independent after Phase 2; uses component data created within
  the story and does not require rod-fitting UI.
- **US3 (P1)**: Independent after Phase 2; rod fit workflows are not required.
- **US4 (P1)**: Depends on package foundation and shared validation/resource
  utilities. It uses rod section concepts from US3 but should implement its
  fitting model independently; integration with the swingweight view can
  follow US3.
- **US5 (P2)**: Depends on working model and rod APIs from US1–US4.
- **US6 (P2)**: Depends on a runnable Streamlit app and CI from US1, US2, US4.

### Parallel Opportunities

- Setup: T002 and T003 can run in parallel; T001 must precede lock generation
  in T004.
- Foundation: T006, T007, and T009 can proceed in parallel after T001/T002;
  T008 follows the test/project skeleton.
- US1: T010 and T011 can run in parallel; T012 and T013 can proceed separately
  before app wiring.
- US2: T017–T22 are independent test files; T023/T024/T028/T029 are separable
  numerical modules, while solver/cast wiring depends on state/domain/operator
  work.
- US3: T036 and the independent implementation modules T037–T039 can proceed
  in parallel; exports/UI follow their APIs.
- US4: T043–T048 are independent test files. T049–T051 and T055 can proceed
  separately; profile fitting depends on elastica/vibration/imaging, and the
  app workflow depends on archive, measurement, fitted-rod, and helper APIs.
- US5: T062–T064 are independent packaged-data groups; T060/T061 can be
  authored before integration but pass after the loaders/package exist.
- US6: Deployment documentation and workflow validation can proceed in
  parallel after the host/deployment integration is identified in T069.
- Polish: T073/T074 can proceed independently; full checks T075–T078 are
  final gates.

### Dependency Graph

```text
T001 -> T002/T003 -> T004
                     |
                     v
              Phase 2: T005-T009
                 /   |   \   \
              US1   US2  US3  US4
                \    |    |   /
                   US5
                    |
          US6 after app + CI ready
                    |
                 Polish
```

Within a story, respect the explicit module dependencies described in its
checkpoint and task descriptions; tests are written before their matching
implementation.

## Parallel Execution Examples

### User Story 1

```text
Task: T010 oscillator behavior tests in tests/unit/test_simple_brick_spring.py
Task: T011 visualization tests in tests/unit/test_simple_brick_spring_helpers.py
Task: T012 numerical model in src/flycastsim/sho/model.py
Task: T013 plotting helpers in src/flycastsim/sho/helpers.py
```

### User Story 2

```text
Task: T017 exact FEM verification tests in tests/unit/test_fem_verification.py
Task: T019 drag tests in tests/unit/test_fem_drag.py
Task: T022 coordinate tests in tests/unit/test_coords.py
Task: T028 drag implementation in src/flycastsim/fem/drag.py
Task: T029 coordinate helpers in src/flycastsim/fem/coords.py
```

### User Story 4

```text
Task: T043 archive tests in tests/unit/test_rod_archive.py
Task: T045 image tracing tests in tests/unit/test_rod_imaging.py
Task: T046 frequency tests in tests/unit/test_rod_vibration.py
Task: T049 elastica solver in src/flycastsim/rod/elastica.py
Task: T051 image tracing in src/flycastsim/rod/imaging.py
Task: T055 archive tools in src/flycastsim/rod/archive.py
```

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Setup (Phase 1).
2. Complete the shared package and app foundations (Phase 2).
3. Complete US1 (Phase 3).
4. Run `tests/unit/test_simple_brick_spring.py` and the app smoke scenario.
5. Stop and review the smallest complete increment before starting the
   scientific FEM reconstruction.

### Full Baseline Reconstruction

1. Implement P1 capabilities in user-story order, preserving independent tests.
2. Treat the six exact FEM verification cases as a strict gate before accepting
   Cast #1 integration.
3. Add rod fitting and packaged artifacts, then validate the installed-wheel
   API and data contract.
4. Configure and verify PR validation/preview and main-branch publication.
5. Run the complete test, lint, docs, package, and quickstart checks.
6. Keep the non-binding future backlog out of this reconstruction; select
   future work through separate feature specifications.
