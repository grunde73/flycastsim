# Research: flycastsim Product Baseline

**Purpose**: Record evidence-backed decisions for reconstructing the current
product. This is a brownfield reconstruction plan, not a proposal to modernize
or extend it.

## Decision: Preserve the existing Python package and application shape

**Decision**: Use a Python >=3.12 library in a `src/` layout, plus the existing
Streamlit application and thin presentation helpers.

**Rationale**: This is the current deployable product boundary. The library is
usable without the UI, the numerical core is plotting-free, and existing
documentation and tests describe these boundaries.

**Alternatives considered**:

- Split the UI and solver into independently deployed services: rejected; no
  current product requirement or external service API requires the split.
- Replace Streamlit or the scientific Python stack: rejected; it would
  introduce behavior and dependencies not present in the baseline.

**Evidence**: `pyproject.toml`, `src/flycastsim/`, `streamlit_app.py`,
`rod_profile_pages.py`, `.github/copilot-instructions.md`.

## Decision: Keep numerical behavior verification-driven

**Decision**: Reimplement the staggered seven-field FEM, generalized-alpha
integration, nonlinear solver, multi-domain junctions, drag, and damping in
the current package boundaries. Accept the numerical core only when all six
exact verification cases and second-order spatial convergence pass.

**Rationale**: These tests define the current scientific contract. The source
documentation also records intentional differences from the paper, including
the staggered scheme and sparse two-colour Jacobian.

**Alternatives considered**:

- Replace the solver with a different discretisation or general-purpose FEM
  package: rejected for the baseline because it risks changing the verified
  solutions and model assumptions.
- Use Cast #1 similarity alone to validate the solver: rejected; Cast #1 is
  only a qualitative demonstration.

**Evidence**: `docs/fem.rst`, `src/flycastsim/fem/__init__.py`,
`src/flycastsim/fem/state.py`, `tests/unit/test_fem_verification.py`.

## Decision: Retain JSON/CSV component data and versioned rod measurements

**Decision**: Store tackle components as JSON metadata plus CSV profiles;
compose ordered components and junctions in a rig JSON; retain the
`flycastsim.rod.measurement/1` YAML measurement format and fitted-rod exports.

**Rationale**: These formats are already used for shipped data, user uploads,
component loaders, profile fitting, and fit provenance.

**Alternatives considered**:

- Introduce a database or new binary profile format: rejected; the current
  product is file-based and has no database-backed workflow.
- Package all raw photos/videos: rejected; the current distribution includes
  derived JSON/CSV profiles while large measurement assets remain in the repo.

**Evidence**: `src/flycastsim/fem/components.py`,
`src/flycastsim/fem/multidomain.py`, `assets/XP590/rod.yaml`,
`src/flycastsim/data/components/cast1/rig.json`, `MANIFEST.in`.

## Decision: Preserve temporary cache behavior without inventing retention

**Decision**: Use shared content-addressed temporary storage for uploaded
archives, forms, and reusable fits, plus a per-session copy for session rods.
Do not define a fixed retention period.

**Rationale**: The user confirmed this behavior as part of the current app.
Content and source fingerprints avoid repeating work and prevent reuse of
results after package code changes. The temporary directory lifetime is
environment-controlled.

**Alternatives considered**:

- Require persistent accounts and per-user storage: rejected; not part of the
  current app.
- Guarantee deletion at session end: rejected for the baseline; it would
  change the confirmed shared-cache behavior.

**Evidence**: `rod_profile_pages.py` (`_shared_root`, `_session_root`,
`_publish`, fit and archive upload flows).

## Decision: Preserve public hosting and branch-event behavior

**Decision**: Reproduce a public hosted Streamlit app. Pull requests perform
validation or a preview without replacing the public app; a merge into `main`
publishes the public app. Keep the docs publishing workflow distinct.

**Rationale**: This matches the clarified product requirement. Existing
repository workflows test pull requests and publish docs from `main`; app
publication is a separate deployment integration.

**Alternatives considered**:

- Local-only app: rejected; public availability is part of the current
  product.
- Deploy pull-request code directly over the production app: rejected by the
  clarification because pull-request work must not replace the public app.

**Evidence**: User-confirmed clarification in `spec.md`, hosted app link in
`README.md`, `.github/workflows/ci.yml`, `.github/workflows/docs.yml`.

## Decision: No invented performance or hosting service levels

**Decision**: Preserve current caching and correctness requirements but set no
new numeric latency, throughput, concurrency, or uptime targets. State that
the public app is resource-limited, fits can be slow, and animations may be
bandwidth-limited.

**Rationale**: No numeric service-level target exists in the current product
documentation. Inventing one would turn a descriptive baseline into a new
product commitment.

**Alternatives considered**:

- Add production-grade uptime and response-time targets: deferred to a future
  operational feature specification if the product scope changes.

**Evidence**: `README.md`, `spec.md`, current Streamlit cache and fit flows.

## Resolved Unknowns

- Runtime and package manager: Python >=3.12 and `uv`.
- Core application type: Python library and Streamlit browser app.
- Persistent database: none; package data and runtime files are used.
- Numerical acceptance: six exact FEM cases plus second-order spatial
  convergence.
- Public app deployment: pull-request validation/preview; merge to `main`
  publishes the public app.
- Upload cache behavior: shared temporary content-addressed cache, no fixed
  retention guarantee.

No unresolved technical-context item blocks the design. Exact deployment
workflow implementation and environment-specific upload limits belong in
implementation tasks; the plan does not invent service-level guarantees.
