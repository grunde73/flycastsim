# architecture Specification

## Purpose
Project-wide constraints on structure, numerics, packaging and security. Each requirement names the check that enforces it, or says that it relies on review.

## Requirements

### Requirement: FEM core is plotting-free
`flycastsim.fem` SHALL NOT import a plotting library or `flycastsim.fem_helpers`, directly or indirectly. Checked by: `uv run lint-imports`.

#### Scenario: A plotting import reaches the FEM core
- **WHEN** a module under `flycastsim.fem` imports `plotly` or `matplotlib`, or imports a module that does
- **THEN** `lint-imports` fails

### Requirement: App uses the public API
`streamlit_app.py` and `rod_profile_pages.py` SHALL NOT import private `flycastsim` names, meaning any module or name with a leading underscore. `flycastsim.fem._cast1_data` is a known exception to be removed, and no others SHALL be added. Checked by: `tests/unit/test_architecture.py::test_app_imports_only_public_api`.

#### Scenario: The app imports a private name
- **WHEN** an app file imports a private `flycastsim` name outside the known exception
- **THEN** the test fails

### Requirement: Computation lives in the package
The Streamlit files MUST remain a thin presentation layer, with real computation in the `flycastsim` package. Checked by: review.

#### Scenario: A change adds computation to the app
- **WHEN** a change adds simulation or fitting logic to an app file
- **THEN** review moves that logic into the package

### Requirement: Exact verification cases hold
Numerical changes SHALL keep the six exact cases and second-order convergence passing, unless a proposal specifies and validates an intentional model change. Checked by: `tests/unit/test_fem_verification.py`.

#### Scenario: A numerical change breaks a verification case
- **WHEN** a change makes a verification case or convergence order fail
- **THEN** the test suite fails and the change does not land without a proposal

### Requirement: Solver reuse is preserved
The solver SHALL keep reusing the factorised Jacobian and caching constant material terms, without changing converged solutions. Checked by: `tests/unit/test_fem_solver.py`.

#### Scenario: Jacobian reuse is lost or changes results
- **WHEN** modified Newton stops saving Jacobian evaluations or converges to a different solution
- **THEN** `test_jacobian_reuse_same_solution_fewer_jacobians` fails

#### Scenario: Material terms are no longer cached
- **WHEN** repeated `material_terms` calls no longer return the cached arrays
- **THEN** `test_material_terms_cached_and_refreshed` fails

### Requirement: FEM field layout uses the helpers
Code MUST address the node-major field layout through the index constants and `Fields` helpers in `fem/state.py`, not hard-coded offsets. Checked by: review.

#### Scenario: A change hard-codes a field offset
- **WHEN** a change indexes the solution vector with a literal offset
- **THEN** review replaces it with the `state.py` helpers

### Requirement: Bundled data ships with the wheel
Every `.json` and `.csv` file under `src/flycastsim/data` SHALL be included in the built wheel. Checked by: `tests/unit/test_architecture.py::test_wheel_ships_bundled_data`.

#### Scenario: A data file is missing from the wheel
- **WHEN** the built wheel lacks a bundled data file
- **THEN** the test fails

### Requirement: Requirements file is generated
`requirements.txt` SHALL match the output of `uv export` for the `app` group. Checked by: `scripts/check_requirements.sh`.

#### Scenario: The lockfile changes without regenerating
- **WHEN** `uv.lock` and `requirements.txt` disagree
- **THEN** the check fails and prints the command that regenerates the file

### Requirement: Physics changes cite their sources
Model changes MUST cite their source equations in docstrings, note simplifications and deviations, and keep the docs "Theory coverage" mapping in sync. Checked by: review.

#### Scenario: A model change lacks a citation
- **WHEN** a change alters a model without citing a source or updating the coverage mapping
- **THEN** review requires both before it lands

### Requirement: User archives use the safe utilities
User-provided archives MUST be handled through `flycastsim.rod.archive`. Checked by: review.

#### Scenario: A change unpacks an uploaded archive
- **WHEN** a change reads a user-provided zip file
- **THEN** review requires it to use `flycastsim.rod.archive`

### Requirement: Security checks run before commit
Commits SHALL pass Ruff's `S` rules and a gitleaks scan of staged changes, and dependency changes SHALL pass `uv audit`. The audit also runs weekly in CI. Checked by: `.pre-commit-config.yaml` and `.github/workflows/security.yml`.

#### Scenario: A dependency has a known vulnerability
- **WHEN** a commit changes `uv.lock` or `pyproject.toml` and the audit reports a known vulnerability
- **THEN** `scripts/check_audit.sh` fails the commit

#### Scenario: A secret is staged
- **WHEN** a staged change contains a credential gitleaks recognises
- **THEN** the commit fails
