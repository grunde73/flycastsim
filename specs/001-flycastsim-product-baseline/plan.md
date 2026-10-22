# Implementation Plan: flycastsim Product Baseline

**Branch**: `spec_driven_dev` | **Date**: 2026-10-19 | **Spec**: [spec.md](./spec.md)

> **Reference only — non-executable.** This clean-room reconstruction outline
> was generated to exercise the Spec Kit workflow. It is not an approved
> implementation plan or authorization to rebuild the software. Use it only as
> context when writing a separately scoped feature plan.

**Input**: Historical baseline documentation request. The plan captures
reconstruction context and does not authorize implementation.

## Summary

Rebuild flycastsim as a Python scientific library with a thin Streamlit
application. Preserve the current 1-D oscillator, 2-D coupled beam-line FEM,
Cast #1, rod swingweight and profile-fitting workflows, packaged tackle data,
public hosted app, and documented deployment behavior. Keep the detailed
physics, input schemas, and verification requirements in the linked companion
documents and data rather than duplicating them here. Do not implement the
non-binding backlog as part of the baseline reconstruction.

## Technical Context

**Language/Version**: Python >=3.12; CI currently pins Python 3.12.

**Primary Dependencies**: NumPy, SciPy, pandas, Plotly, Pillow, PyYAML,
Streamlit, and `streamlit-image-coordinates`; Sphinx, pytest, and Ruff are
development/documentation tools.

**Storage**: No database. Use package resources for installed JSON/CSV tackle
data, repository files for large reference measurements, and temporary
filesystem storage for app uploads, cached fits, and cached simulations.
Uploaded datasets and reusable fits are shared by content in temporary
storage; the product makes no fixed retention promise.

**Testing**: pytest unit and verification suite; Ruff lint; Sphinx HTML
documentation build. Numerical acceptance includes six exact FEM verification
cases and second-order spatial convergence.

**Target Platform**: Python >=3.12 on supported desktop/server environments;
Linux CI; browser-based local Streamlit app and a public hosted Streamlit app.
GitHub tasks validate or preview pull requests, while merges into `main`
publish the public app.

**Project Type**: Python library plus scientific web application and packaged
data.

**Performance Goals**: No numeric latency, throughput, concurrency, or
availability target is defined. Preserve the current solver reuse/caching
behavior and correctness; the public app may have slow rod fits and
bandwidth-limited animations.

**Constraints**: Preserve the established API surfaces, source layout, physical
units, measured data provenance, safe archive extraction, plot-free FEM core,
node-major interleaved FEM state, and documented deviations from the source
theory. Packaged data must be included in wheel/sdist outputs; large measurement
assets remain repository-only. The future backlog is out of scope.

**Scale/Scope**: Three interactive app areas, one installable Python package,
three bundled fitted rods, one packaged Cast #1 rig, and five primary user
journeys plus public app access. No product-level maximum archive size, frame
count, or concurrent-user count is specified; hosting limits apply.

## Constitution Check

| Principle / constraint | Gate | Plan alignment |
|---|---|---|
| Scientific and Numerical Integrity | PASS | Reproduce cited equations and deliberate deviations; preserve six exact cases and second-order convergence. |
| Library and UI Separation | PASS | Keep computation in `src/flycastsim/`; Streamlit and plotting adapters remain outside the FEM numerical core. |
| Verification as Contract | PASS | Use focused pytest coverage and the FEM verification suite as acceptance tests. |
| Reproducible Data | PASS | Preserve units/provenance, package JSON/CSV data, and use the established safe archive behavior. |
| Small, Explicit Changes | PASS | Plan reconstruction scope only; treat backlog items as separate future specifications. |
| Technical constraints | PASS | Python >=3.12, `uv`, seven-field interleaving helpers, solver reuse, manifest, and theory docs remain required. |

No constitution violations or unresolved clarification gates remain.

## Project Structure

### Documentation (this feature)

```text
specs/001-flycastsim-product-baseline/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── python-api.md
│   ├── component-and-rig-data.md
│   ├── rod-measurements.md
│   └── application-and-deployment.md
├── checklists/
│   └── requirements.md
└── tasks.md                 # Created by /speckit-tasks, not by this plan
```

### Source Code (repository root)

```text
src/flycastsim/
├── sho/                     # 1-D forced oscillator and display helpers
├── fem/                     # continuum solver, domains, components, casts
├── rod/                     # swingweight, fitting, measurement, archive tools
├── data/                    # packaged component and example-rod JSON/CSV
└── fem_helpers.py           # app-facing result visualization helpers

streamlit_app.py             # top-level app and navigation
rod_profile_pages.py         # rod comparison and upload/fit UI
assets/                      # large, repository-only measurements/reference data
tests/unit/                  # focused tests and FEM verification cases
docs/                        # theory, methods, data schema, API documentation
.github/workflows/           # CI/docs workflows; app deployment integration
pyproject.toml
uv.lock
MANIFEST.in
```

**Structure Decision**: Retain the current single-repository Python src layout.
It separates scientific computation from UI code while keeping the installable
library, Streamlit app, packaged profiles, reference assets, tests, and docs
under one versioned project. No separate frontend/backend service or database
is justified by the current product contract.

## Architecture and Design

1. **Scientific library**: Implement the oscillator, FEM state/domain,
   operators, solver, cast assembly, rod estimation/fitting, and data loaders
   as independent package capabilities. Keep plotting adapters and app widgets
   out of the numerical core.
2. **Continuum data flow**: Load ordered tackle components, interpolate their
   profiles onto subdomains, connect them with pinned/welded junctions, solve
   the seven-field system, and reconstruct positions and cast outputs.
3. **Rod fitting flow**: Parse measurement metadata and image/frequency/CCS
   inputs; trace and calibrate frames; fit physical profiles and nuisance
   parameters; export a provenance-bearing fitted-rod package.
4. **Streamlit interface**: Expose the 1-D model, Cast #1, and rod tools.
   Trigger expensive cast/fit work explicitly, show progress/errors, and
   reuse cached results. Session-fitted rods remain available to the current
   session.
5. **Data persistence**: Use package resources for shipped rig/profile data,
   repository `assets/` for large measurements, and shared/session temporary
   directories for runtime work. Preserve content-addressed cache reuse and
   do not promise a fixed cache-retention period.
6. **Delivery**: Run checks on pull requests; merge to `main` publishes the
   public app. Keep the GitHub Pages documentation workflow separate from app
   publication.

## Validation Strategy

- Recreate documented examples for the public library, app flows, and bundled
  rods using the companion references.
- Run focused model, rod, archive, and app-facing tests as each subsystem is
  reconstructed.
- Treat `tests/unit/test_fem_verification.py` and its exact solutions and
  convergence assertions as mandatory acceptance gates for the FEM.
- Verify wheel/sdist package contents include JSON/CSV component data and
  exclude repository-only measurement assets.
- Exercise zip upload validation, tracing preview, fit reuse, and per-session
  fitted-rod availability.
- Verify pull-request validation/preview does not replace the public app and
  a merge to `main` publishes it.
- Run `uv run ruff check .` and `uv run --extra docs --directory docs make html`
  at the repository-appropriate validation stage.

## Complexity Tracking

No constitution violations. No additional service, database, frontend
framework, or persistence abstraction is planned.
