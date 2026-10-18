# Copilot instructions for flycastsim

`flycastsim` is a Python library + Streamlit web app for simulating fly casts. It
contains a simple 1-D brick–spring–car oscillator model and a 2-D continuum
(finite-element) engine that solves a coupled rod + fly-line beam-line, validated
against six exact verification cases. It also has rod tools: a **swingweight**
estimator and a **stiffness/mass profile fit** from filmed static bend tests,
tip-mass frequency tests and CCS data, with three fitted rods bundled.

## Environment, build, test, lint

The project is managed with [uv](https://docs.astral.sh/uv/); Python `>=3.12`.

- Install everything: `uv sync --all-extras` (CI uses this). The `dev` and
  `app` dependency groups are installed by default.
- Run the app: `uv run streamlit run streamlit_app.py`
- Fit a measured rod: `uv run python examples/rod_profile_fit.py --rod assets/XP590`
  (`--preset quick|full`, `--install` copies the result into the package data)
- Run the full test suite: `uv run pytest`
- Run one test file: `uv run pytest tests/unit/test_fem_verification.py`
- Run one test: `uv run pytest tests/unit/test_fem_verification.py::<test_name>`
- Build the docs: `uv run --extra docs --directory docs make html`

Linting/formatting uses [ruff](https://docs.astral.sh/ruff/) (configured in
`pyproject.toml`):

- Lint: `uv run ruff check .`
- Auto-fix: `uv run ruff check --fix .`
- Format: `uv run ruff format .`

Ruff config notes: `__init__.py` files ignore `F401` (they re-export the public
API); tests ignore `E402`/`E741` (section-local imports and short physics symbols
like `l` = length); `docs/` and `*.ipynb` are excluded. Keep `uv run ruff check .`
clean.

`requirements.txt` is auto-generated via `uv export` (for plain-pip / Streamlit
Cloud); regenerate it rather than editing by hand.

## Architecture (the big picture)

The installable package lives under `src/flycastsim/` (src layout). Three model
subpackages, all re-exported through `src/flycastsim/__init__.py`:

- `sho/` — the simple 1-D forced harmonic oscillator (`brick_spring_simple`),
  plus Matplotlib plotting/animation helpers. Ported from old MATLAB (`sho/matlab/`).
- `fem/` — the continuum engine. This is the heart of the project. Pipeline:
  `domain.py` (build `Subdomain`/`MultiDomain` beam geometry) → `operators.py`
  (staggered finite-difference spatial operators + `BoundaryConditions`) →
  `state.py` (packs the **7 coupled fields** into a flat solution vector) →
  `genalpha.py` + `solver.py` (generalised-alpha time integration with
  Newton–Raphson and a sparse two-colour finite-difference Jacobian via SuperLU)
  → `cast.py` / `multidomain.py` (high-level cast simulations). `analytic.py`
  holds the exact solutions used by the verification tests; `drag.py` is the
  Reynolds air-drag law; `coords.py` maps fields to physical x/y positions;
  `components.py` assembles data-driven tackle components (rod/line/leader as
  JSON metadata + CSV profile tables, wired together by a `rig.json`) into a
  `MultiDomain`.
- `rod/` — rod parameters:
  `swingweight.py` (butt-axis moment of inertia from per-section measurements);
  the stiffness/mass profile fit described in `docs/rod_profile.rst`:
  `elastica.py` (static large-deflection solver; `solve_cantilever_fd` is the
  fixed-mesh banded-Newton variant the fit uses), `vibration.py` (tip-mass
  frequency), `imaging.py` (rod centre line from photos), `profile_fit.py`
  (parametrisations, image transform, joint least-squares fit),
  `measurement.py` (`rod.yaml` loader, `fit_rod` presets, `export_fit`,
  `create_measurement`), `fitted.py` (`FittedRod`, `load_fitted_rods`),
  `archive.py` (safe zip handling). Cast #1 takes a fitted rod via
  `simulate_cast1(rod=..., rod_diameter=...)`.

`streamlit_app.py` (repo root) is the UI; the *Rod parameters* views
(Stiffness profiles, Upload & fit) live in `rod_profile_pages.py`. Both only
import the public API from `flycastsim` / `flycastsim.fem` / `flycastsim.rod` —
keep app logic thin and put real computation in the package. Slow results
(Cast #1 runs, traces, fits) are cached on disk keyed by a fingerprint of the
package source (`rod_profile_pages.code_version`).

The model implements Ekander, Perkins & Richards (*Sports Engineering* 2025) /
the theory at willmanco.se. The docstrings in `fem/__init__.py` and
`fem/state.py` document where this implementation **deliberately deviates** from
the paper (e.g. staggered vs. centered scheme, sparse-colouring vs. banded
Jacobian). Read those before changing the numerics, and keep the `docs/`
"Theory coverage" mapping in sync with what is actually implemented.

## Conventions specific to this codebase

- **FEM field layout**: the 7 fields (`u_s, u_n, F_s, F_n, phi, nu_z, Gamma_z`)
  use a **node-major / interleaved** flat vector — field `f` at node `i` lives at
  `X[i * NFIELDS + f]`. Use the index constants and `Fields` helpers in
  `state.py`; never hard-code offsets.
- **Verification-driven changes**: numerical changes must keep
  `tests/unit/test_fem_verification.py` passing (the six exact cases, including
  second-order convergence checks). Treat these as the spec.
- Tests live in `tests/unit/` and are named `test_<area>.py`.
- **Bundled data** (rod/line/leader profiles, example rods, fitted rods in
  `data/components/fitted_rods/<ROD>/`) lives in `src/flycastsim/data/` as
  `.json`/`.csv` and is shipped with the wheel — load it via the package
  loaders (e.g. `load_rig`, `load_example_rods`, `load_fitted_rods`), and add
  new packaged data files to `MANIFEST.in`. Large reference assets (videos,
  scraped pages, cast frames, rod measurement data sets in `assets/<ROD>/`)
  live in the repo root and are *not* packaged.
- **Solver performance**: `integrate` reuses the factorised Jacobian across
  Newton iterations and steps (modified Newton) and `Subdomain.material_terms`
  caches constant residual terms; keep both when changing the numerics (the
  converged solutions must not change).
- **Keep the numerical core plotting-free**: `flycastsim.fem` must not import
  any plotting library. Plotly helpers for the app live in `fem_helpers.py`
  (and `rod/helpers.py`, `sho/helpers.py` for their models).
- Physics references (papers, source equations) are cited in docstrings — when
  adding/altering a model, cite the source and note any simplification, matching
  the existing docstring style.
