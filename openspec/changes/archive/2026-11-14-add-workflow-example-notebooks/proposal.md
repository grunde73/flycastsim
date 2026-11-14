# Proposal

## Why

The five-step workflow (1-D model, rod, line and leader, casting parameters, cast simulation) is now explicit in the app, but the library has no runnable examples that follow it. The only example notebook, `flysim_examples.ipynb`, covers the 1-D model alone and no longer runs: it imports the package under its old name `flycast`. Nothing checks that example notebooks keep working.

## What Changes

Proposal-required category: new capability. The example notebooks have no capability spec, and this change adds one. Examples would not need a proposal on their own.

- Add one notebook per workflow step under `examples/notebooks/`:
  - `01_simple_1d_model.ipynb`: the standalone brick-spring-car model.
  - `02_rod_characteristics.ipynb`: swingweight from section measurements, the measured rods and their consistency check, and the fitted stiffness and mass profiles.
  - `03_line_and_leader.ipynb`: loading line and leader components, scaling a line to an AFTM weight, and assembling a rig.
  - `04_casting_parameters.ipynb`: the casting stroke as a rod-butt angle over time, for the idealised stroke and the Cast #1 stroke.
  - `05_simulate_cast.ipynb`: simulating the generic cast and Cast #1, and reading the results.
- Add `complete_workflow.ipynb`, which runs steps 2 to 5 in sequence: pick a fitted rod, pick a line weight, look at the stroke, simulate Cast #1 and compare with the footage.
- Remove the broken `flysim_examples.ipynb`. Its content moves into `01_simple_1d_model.ipynb`.
- Add a test that executes every example notebook, and checks that they import only the public API and are committed without outputs.
- Add the notebook tools to the `dev` dependency group, and point the README and docs at the new notebooks.

Not included:

- New library features. Where a step is not yet a real step, the notebook says so:
  - Casting parameters cannot be loaded from a file or passed to `simulate_cast1`; the stroke is built into the Cast #1 simulation.
  - Only one line and one leader are bundled.
- Running a rod fit in the notebooks by default. A fit takes too long for a test, so the fit cell is switched off and the notebook points to `examples/rod_profile_fit.py`.
- `flycast_dev_explore.ipynb`, which stays as development scratch.
- Rendering the notebooks into the Sphinx docs.

## Capabilities

### New Capabilities

- `example-notebooks`: which example notebooks the repo provides, what they cover, and the guarantees that keep them runnable.

### Modified Capabilities

None.

## Impact

- `examples/notebooks/`: six new notebooks.
- `flysim_examples.ipynb`: removed.
- `tests/unit/test_example_notebooks.py`: new test. It adds a few seconds to the test suite, mostly from the Cast #1 runs.
- `pyproject.toml` and `uv.lock`: `ipykernel` and `nbclient` in the `dev` group. They are not installed in the Streamlit deployment: `requirements.txt` is exported from the `app` group alone and does not change, and a test checks that.
- `README.md`, `docs/index.rst`, `docs/dev.rst` and `.github/copilot-instructions.md`: references to the notebooks.
- No package code, public API or data format changes.
