# Python Library Contract

The public library is importable as `flycastsim` on Python >=3.12 and remains
usable without Streamlit.

## Public capability groups

- `flycastsim.brick_spring_simple` computes tabular results for the 1-D
  oscillator; `flycastsim.plot_brick_spring` and
  `flycastsim.animate_brick_spring` provide optional visualization.
- `flycastsim.fem` exposes domain construction, state/field helpers,
  boundary conditions, static and dynamic solvers, component and rig loaders,
  drag, coordinate reconstruction, and cast entry points.
- `flycastsim.fem.simulate_cast` runs a configured continuum cast;
  `flycastsim.fem.simulate_cast1` runs the bundled Cast #1 scenario, with
  overrides for the rod and simulation parameters.
- `flycastsim.rod` exposes swingweight calculations and result/section types,
  static elastica and vibration solvers, image tracing, profile fitting,
  measurement loading, fitted-rod loading, and safe archive utilities.

Documented rod entry points include `compute_swingweight` (also exported from
the package as `swingweight`), `load_example_rods`, `fit_rod`,
`load_rod_measurement`, `export_fit`, and `load_fitted_rods`.

## Behavioral requirements

- Numerical functions must return computable results independently of UI
  widgets or Streamlit session state.
- Inputs with invalid geometry, profile shape, or unsupported choices must
  surface errors; they must not be silently converted to success-shaped data.
- Numerical state layout and field access must use the helpers in
  `flycastsim.fem.state`.
- The FEM numerical modules must not import plotting libraries.
- Physics conventions and deliberate differences from the source equations
  are defined by `docs/fem.rst`, the package docstrings, and the six-case
  verification suite.

## Compatibility and verification

Public functions and data classes must preserve documented names and units.
Run the focused relevant unit tests; any numerical implementation must pass
`tests/unit/test_fem_verification.py` and its convergence assertions.

The companion API documentation and the current package `__init__.py`
re-exports are the authoritative detailed contract for full argument and
return-value signatures.
