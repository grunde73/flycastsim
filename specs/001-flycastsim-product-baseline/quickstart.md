# Quickstart: flycastsim Reconstruction Validation

This guide defines local checks for a reconstructed baseline implementation.
Detailed contracts are in `contracts/`; model equations and measurement
conventions remain in the companion documents listed in `spec.md`.

## Prerequisites

- Python >=3.12 (CI pins Python 3.12).
- `uv`.
- A browser for the Streamlit UI.

## Setup

From the repository root:

```sh
uv sync --all-extras
```

Expected: package, app, development, and documentation dependencies install
into the project environment.

## Run the application

```sh
uv run streamlit run streamlit_app.py
```

Expected: the browser opens the app with the 1-D model, Cast #1, and Rod
parameters sections.

## Validate the Python package and numerical core

```sh
uv run pytest
uv run ruff check .
```

For the continuum acceptance gate:

```sh
uv run pytest tests/unit/test_fem_verification.py
```

Expected: all six exact cases and the second-order convergence check pass.

## Validate the rod workflow

Use the XP590 measurement set as a representative input:

```sh
uv run python examples/rod_profile_fit.py --rod assets/XP590 --preset quick
```

Expected: the measurement loads, the selected fit runs, and a fitted rod
artifact with profile data and a fit summary is produced. The fit is
computationally expensive; quick preset is for a smoke check, not a substitute
for quantitative fit review.

In the app, verify that a rod archive can be uploaded, traces previewed, a fit
started with progress, and the resulting rod downloaded and selected within
the current session. Repeat the same input/preset where a cached result exists
to verify reuse.

## Validate documentation and packaging

```sh
uv run --extra docs --directory docs make html
uv build
```

Expected: Sphinx generates the HTML documentation; distribution artifacts
include the packaged JSON/CSV profiles and do not bundle large repository
measurement assets.

## Validate hosted deployment behavior

1. A pull request targeting `main` runs validation or preview work without
   replacing the public app.
2. A merge into `main` publishes the updated public app.
3. Open the public URL and confirm the Streamlit application loads.

The actual preview mechanism and deployment credentials are environment
configuration; no secrets or deployment credentials belong in the repository.
