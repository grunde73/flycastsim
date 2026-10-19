# flycastsim Constitution

## Core Principles

### I. Scientific and Numerical Integrity
Model behavior MUST be grounded in the cited theory, source equations, or
measured data. A numerical change MUST preserve the six exact FEM verification
cases and second-order convergence unless an intentional model change is
explicitly specified and its changed behavior is validated. Documentation MUST
identify deliberate simplifications and deviations from source models.

### II. Library and UI Separation
Simulation and rod-characterisation computation MUST live in the installable
`flycastsim` package. Streamlit code MUST remain a thin presentation layer and
use the package's public API. The `flycastsim.fem` numerical core MUST remain
free of plotting-library imports.

### III. Verification as Contract
New behavior MUST have focused automated tests. Numerical work MUST be checked
against relevant physical or analytic references, not only against another
implementation path. Changes to the continuum solver MUST retain the
verification-driven tests as acceptance criteria.

### IV. Reproducible Data
Packaged component and fitted-rod data MUST be loaded through the package
loaders and included in distribution manifests. Measurement provenance,
physical units, and assumptions MUST remain explicit. User-provided archives
MUST be handled using the established safe archive utilities.

### V. Small, Explicit Changes
Changes MUST address the requested behavior without unrelated refactoring or
unnecessary abstractions. Errors MUST be surfaced rather than hidden by broad
catches or success-shaped fallbacks. Public behavior, compatibility
constraints, and any intentional behavior changes MUST be stated in the
specification and covered by validation.

## Technical Constraints

- The package uses Python >=3.12 and is managed with `uv`.
- The FEM solution vector is node-major and interleaves seven fields. Code
  MUST use the field/index helpers in `fem/state.py`.
- Solver changes MUST preserve Jacobian reuse and cached constant material
  terms unless a specification explicitly changes the performance contract.
- Add new packaged data files to `MANIFEST.in`; large measurement assets under
  `assets/` remain repository data rather than installed package data.
- Physics changes MUST cite their source equations in docstrings and keep the
  documentation's theory-coverage mapping synchronized with implementation.

## Development Workflow

- Run focused tests for the changed behavior. For numerical changes, run
  `uv run pytest tests/unit/test_fem_verification.py` and other affected tests.
- Run `uv run ruff check .` for Python changes.
- Build the Sphinx documentation when documentation or its references change:
  `uv run --extra docs --directory docs make html`.
- Specifications MUST distinguish observed current behavior from proposed
  future behavior. Plans MUST reuse the repository's architecture, dependencies,
  and test conventions unless the specification explicitly changes them.

## Governance

This constitution records project-wide constraints for future specifications
and implementation work. Amendments MUST state the reason for the change and
increment the version: MAJOR for incompatible principle changes, MINOR for new
or materially expanded principles or sections, and PATCH for non-semantic
clarifications. Reviews MUST check changed work against the applicable
principles and technical constraints. If a specification intentionally
deviates, it MUST identify the conflict and define how the deviation will be
validated.

**Version**: 1.0.0 | **Ratified**: 2026-10-19 | **Last Amended**: 2026-10-19
