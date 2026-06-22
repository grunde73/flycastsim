# Copilot instructions for flycastsim

`flycastsim` is a Python library + Streamlit web app for simulating fly casts. It
contains a simple 1-D brick–spring–car oscillator model and a 2-D continuum
(finite-element) engine that solves a coupled rod + fly-line beam-line, validated
against six exact verification cases. It also has a rod **swingweight** estimator.

## Environment, build, test, lint

The project is managed with [uv](https://docs.astral.sh/uv/); Python `>=3.12`.

- Install everything: `uv sync --all-extras` (CI uses this).
- Run the app: `uv run streamlit run streamlit_app.py`
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
  Reynolds air-drag law; `coords.py` maps fields to physical x/y positions.
- `rod/` — `swingweight.py` estimates a rod's butt-axis moment of inertia from
  per-section measurements (`RodSection` → `compute_swingweight`).

`streamlit_app.py` (repo root) is the UI. It only imports the public API from
`flycastsim` / `flycastsim.fem` / `flycastsim.rod` — keep app logic thin and put
real computation in the package.

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
- **Bundled data** (rod/line/leader profiles, example rods) lives in
  `src/flycastsim/data/` as `.json`/`.csv` and is shipped with the wheel — load
  it via the package loaders (e.g. `load_rig`, `load_example_rods`), and add new
  packaged data files to `MANIFEST.in`. Large reference assets (videos, scraped
  pages, cast frames) live in the repo-root `data/` and are *not* packaged.
- Physics references (papers, source equations) are cited in docstrings — when
  adding/altering a model, cite the source and note any simplification, matching
  the existing docstring style.
