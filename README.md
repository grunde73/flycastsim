# flycastsim
A web-app and library with functions for simulating flycasts.

The package is a work in progress, and it will (maybe) be
further developed when time and motivation permits.

## What is in it
- **Simple 1-D model** — a *brick-spring-car* toy model of casting.
- **Continuum (finite-element) engine** (`flycastsim.fem`) — a coupled
  rod + fly line + leader beam-line with bending, tension and gravity, optional
  Reynolds-number air drag and Kelvin-Voigt material damping, validated against
  six exact verification cases. It follows Ekander, Perkins & Richards,
  *Sports Engineering* (2025), and the theory at
  [willmanco.se](https://www.willmanco.se); the
  [FEM docs](https://grunde73.github.io/flycastsim) map which parts of that
  model are implemented, simplified or still planned.
- **Cast #1** — reproduces a real recorded cast from Løvoll & Borger's
  *The Rod & The Cast*: the rod is driven by a rod-butt angle sweep fitted to
  the footage (with a forward hand haul), the full ~12.7 m line + leader starts
  laid out behind the caster ~5° below horizontal, and the simulated rod chord
  length is compared against the measured curve and the high-speed video
  frames. The rod can be the tabulated T&T Paradigm profile or one of the
  **measured (fitted) rods** below.
- **Rod parameters** (`flycastsim.rod`):
  - **Swingweight** — the moment of inertia about the rod butt from simple
    per-section measurements (Løvoll & Angus, *Measuring fly rod
    "swingweight"*, 2008), with ferrule-overlap and reel-seat/grip
    corrections.
  - **Stiffness and mass profiles** — the bending stiffness EI(s) and mass per
    length μ(s) along a rod, fitted to a **static bend test** filmed frame by
    frame (the rod centre line is traced in every image and a large-deflection
    *elastica* model is fitted to all frames at once), a **tip-mass frequency
    test**, the **Common Cents System** point and, when available, section
    masses. Three measured rods (T&T Paradigm 905-3, Sage XP 590-4, Sage TCR
    590-4) ship with the package as ready-to-use FEM components.

The app is written in Python and runs in the browser using
[Streamlit](https://streamlit.io/). Its sections are the 1-D model, the
sample fly cast / Cast #1 (choose the rod), and *Rod parameters* with three
views: **Swingweight**, **Stiffness profiles** (compare the fitted rods) and
**Upload & fit** (fit your own rod from a zipped data set or a guided form,
with click-to-place calibration points, and download the result). The app is
also publicly available at
[https://share.streamlit.io/grunde73/flycastsim/main](https://share.streamlit.io/grunde73/flycastsim/main)
(the animations may not work 100% as intended due to limited bandwidth, and
long fits are slow there).

Up-to date documentation is found at:
[https://grunde73.github.io/flycastsim](https://grunde73.github.io/flycastsim)


## Quickstart
The project is managed with [uv](https://docs.astral.sh/uv/). Install uv
(see the [uv installation docs](https://docs.astral.sh/uv/getting-started/installation/)),
then from the terminal do:
```shell
$ git clone git@github.com:grunde73/flycastsim.git
$ cd flycastsim
$ uv sync
$ uv run streamlit run streamlit_app.py
```
This creates an isolated virtual environment (`.venv`), installs the
`flycastsim` package together with the app and development dependencies (the
default dependency groups), and launches the app in your default browser at
http://localhost:8501. uv automatically provisions a compatible Python
interpreter (>= 3.12) for you. `uv sync --all-extras` also installs the
documentation tools.

A `requirements.txt` (auto-generated with `uv export`) is also provided for
environments that use plain `pip`, such as Streamlit Community Cloud:
```shell
$ pip install -r requirements.txt
$ streamlit run streamlit_app.py
```

## Examples
- `flysim_examples.ipynb` — Jupyter notebook with examples of using the
  package.
- `examples/rod_profile_fit.py` — fit a measured rod end to end
  (`uv run python examples/rod_profile_fit.py --rod assets/XP590 --preset quick`).
- Using a fitted rod in a simulation:
  ```python
  from flycastsim.fem import simulate_cast1
  from flycastsim.rod import load_fitted_rods

  rods = {r.id: r for r in load_fitted_rods()}        # PA905, TCR590, XP590
  result = simulate_cast1(rod=rods["XP590"].component, rod_diameter="cast1")
  ```

The measurement data sets of the bundled rods (bend-test images, frequency
tests, `rod.yaml` descriptions) are in `assets/<ROD>/`.


## Documentation
The full package documentation is found in the [docs](./docs/)
folder, and it is written in reStructuredText
for [Sphinx](https://www.sphinx-doc.org/en/master/), with the
[Read The Docs theme](https://sphinx-rtd-theme.readthedocs.io/en/stable/) and
[sphinx-autoapi](https://sphinx-autoapi.readthedocs.io/en/latest/index.html)
to generate the API documentation from the source code.

Build and open the documentation with:
```shell
$ uv run --extra docs --directory docs make html
$ open docs/build/html/index.html
```

The docs are also available online here:
[https://grunde73.github.io/flycastsim](https://grunde73.github.io/flycastsim)


## Disclaimer
> "Essentially, all models are wrong, but some are useful."
> George E. P. Box

Remember, models are just models. So be critical and aware
of the limitations and assumptions of all models, including
the ones found here :-D
