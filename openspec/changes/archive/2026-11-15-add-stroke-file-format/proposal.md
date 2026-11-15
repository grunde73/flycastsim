# Proposal

## Why

Workflow step 4, "load, create or extract casting parameters", has no data
format. The only real stroke, Cast #1, is hard-coded in the private module
`flycastsim.fem._cast1_data`, and `simulate_cast1` cannot take any other
stroke. A stroke file format is the first step towards strokes from video,
sensors or a hand-drawn curve, and it lets steps 2 to 5 run with a loaded
stroke.

Proposal-required categories: new capability, data format change, public API
change, and numerics that can change converged solutions (the Cast #1 results
move slightly, see below).

## What Changes

- Add a stroke data format: a `stroke.json` metadata file plus a `stroke.csv`
  table with time, rod-butt angle and, optionally, hand position.
- Add a public API in `flycastsim.fem`: a `Stroke` object, `load_stroke`,
  `save_stroke` and `bundled_stroke_path`.
- Bundle the Cast #1 stroke as data in that format, sampled every 2.5 ms.
- Add a `stroke` argument to `simulate_cast1`. It accepts a bundled name, a
  path or a `Stroke`, and defaults to the bundled Cast #1 stroke.
- Remove the hard-coded stroke drive (angle table, hand-path formula) from
  `_cast1_data`. `cast1_stroke()` keeps working and reads the bundled stroke.
- Warn when a loaded stroke is sampled too coarsely to give reliable results.
- **Numerics change, accepted by the owner:** the Cast #1 hand path changes
  from a formula to an interpolated table, and the 12 digitised angle points
  are resampled onto the same table. Measured with a trial run against the
  current code at the default settings:

  | Quantity | Largest change |
  |---|---|
  | Rod chord length | 0.011 mm |
  | Tip deflection | 0.10 mm |
  | Any node position before RSP | 0.013 mm |
  | Any node position, whole cast | 1.3 mm |

  The six exact verification cases do not use the stroke and are unaffected.
- Update the step 4 notebook and the complete workflow notebook to load a
  stroke from a file and pass it to the simulation.

Not in this change:

- A public home for the AFTM line table. The app's private import of
  `_cast1_data` stays for that reason, so the known exception in the
  architecture spec remains.
- A "cast setup" file. The start time and the initial line layout stay as
  `simulate_cast1` arguments.
- Extracting strokes from video or sensors, and tools to resample or smooth a
  coarse stroke.
- A stroke argument on the generic `simulate_cast`.

## Capabilities

### New Capabilities
- `cast-stroke`: the stroke data format, loading and saving strokes, the
  bundled Cast #1 stroke, and driving the Cast #1 simulation with a stroke.

### Modified Capabilities
- `example-notebooks`: the requirement "Notebooks state the limits of each
  step" says the step 4 notebook states that a stroke cannot be loaded from a
  file. That limit goes away, so its scenario changes.

## Impact

- New code: `src/flycastsim/fem/stroke.py`, exported from `flycastsim.fem`.
- New data: `src/flycastsim/data/strokes/cast1/stroke.json` and `stroke.csv`.
- Changed code: `fem/cast.py` (`simulate_cast1`, `cast1_stroke`),
  `fem/_cast1_data.py` (stroke drive removed), `streamlit_app.py` (rod-butt
  angle now from the public stroke API).
- Tests: new `tests/unit/test_fem_stroke.py`, a frozen Cast #1 reference file
  under `tests/unit/data/`, and updates to `tests/unit/test_fem_cast.py`.
- Notebooks: `04_casting_parameters.ipynb`, `complete_workflow.ipynb`.
- Docs: `docs/fem.rst`, `README.md`, `.github/copilot-instructions.md`.
- No new dependencies. `requirements.txt` does not change.
