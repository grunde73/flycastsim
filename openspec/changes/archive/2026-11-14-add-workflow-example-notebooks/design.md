# Design

## Context

See proposal.md for the motivation. The facts that shape the approach:

- The public API already covers every step. No private name is needed:
  - Step 1: `brick_spring_simple`, `plot_brick_spring`.
  - Step 2: `swingweight`, `load_example_rods`, `load_measured_rods`, `check_consistency`, `load_fitted_rods`, `plot_fitted_profiles`, `fitted_rods_table`, and for the fit `load_rod_measurement`, `fit_rod`, `export_fit`.
  - Step 3: `load_component` (with `aftm_weight`), `load_rig`, `bundled_rig_path`, `copy_example_rig`.
  - Step 4: `casting_stroke`, `cast1_stroke`.
  - Step 5: `simulate_cast`, `simulate_cast1` (with `rod=`, `aftm_weight=`), and the plot helpers `plot_cast_snapshots`, `plot_chord_comparison`, `plot_tip_deflection`, `plot_cast_speeds`.
- `simulate_cast1` has no stroke argument, and no stroke file format exists. The app reads the AFTM line mass through the private `_cast1_data` module, which the notebooks must not use.
- Measured on this machine: a default `simulate_cast1` run takes about 1.3 s and `simulate_cast` about 0.3 s. A rod fit takes far longer.
- No notebook tooling is installed. Ruff excludes `*.ipynb`. The plot helpers return Plotly figures.
- CI runs `uv sync --all-extras` and `uv run pytest`.

## Goals / Non-Goals

**Goals:**

- A reader can open one notebook for the step they care about and run it as is.
- A notebook that stops working fails the test suite.
- The notebooks add little time to the test suite.

**Non-Goals:**

- Changing the library to make steps 3 and 4 fuller. The notebooks describe the gaps.
- Publishing rendered notebooks in the Sphinx docs.
- Linting or formatting notebook code.

## Decisions

### Location and names

The notebooks go in `examples/notebooks/`, next to `examples/rod_profile_fit.py`, with a two-digit step prefix so they sort in workflow order. The alternative, the repo root where the old notebook sits, would add six files to an already crowded root.

### Each notebook is self-contained

A step notebook loads its inputs from bundled data and does not read files written by another notebook. That keeps each one runnable alone and lets the test run them in any order. `complete_workflow.ipynb` passes objects between its sections in memory: the fitted rod and the line weight go straight into `simulate_cast1`.

The alternative, notebooks that write parameter files for the next step, matches the workflow idea more closely. It needs a stroke file format that does not exist, so it waits for that change.

### The test executes the notebooks with `nbclient`

`tests/unit/test_example_notebooks.py` collects `examples/notebooks/*.ipynb` and runs each with `nbclient` in a fresh `python3` kernel, with the working directory set to the notebook's folder and a timeout per cell. Collecting from the folder means a new notebook is tested without editing the test. `ipykernel` and `nbclient` are added to the `dev` group, which CI installs.

The `dev` group is the right place because the Streamlit deployment installs from `requirements.txt`, which is exported from the `app` group alone (`uv export --no-default-groups --group app`). It holds no `dev` tools today, such as `pytest` or `ruff`, and the notebook tools follow the same route. A test checks that they stay out of `requirements.txt`. A separate `notebooks` group was considered and left out: it would keep the tools out of the deployment equally well, but CI and contributors would need an extra flag to run the full test suite.

Alternatives considered:

- `pytest --nbmake`. It needs a pytest plugin and a separate invocation, where a plain test keeps one `uv run pytest`.
- Converting notebooks to scripts and running those. It skips the kernel, so it would miss problems with figure display.

The same test file checks the imports and the outputs by reading the notebook JSON, reusing the approach of `test_app_imports_only_public_api`.

### Figures are displayed, not asserted

Notebooks end plotting cells with the figure object so Jupyter displays it. The test only requires the cells to run without an error. It does not compare figures, because figure contents are covered by the library's own tests.

### The slow parts are kept out of the default run

- The rod fit cell in `02_rod_characteristics.ipynb` is guarded by `RUN_FIT = False`. The notebook explains the flag and shows the already fitted rods through `load_fitted_rods`.
- Cast runs use the default settings. With about four Cast #1 runs across `05_simulate_cast.ipynb` and `complete_workflow.ipynb`, the test adds roughly ten seconds including kernel start-up.

### Notebooks are stored without outputs

The notebooks are saved with outputs and execution counts cleared, and the kernel name set to `python3`. The test enforces the cleared outputs. A pre-commit hook such as `nbstripout` was considered and left out: the test already catches the problem, and a hook adds a dependency.

### The old notebook is removed, not fixed

`flysim_examples.ipynb` has four cells, all about the 1-D model, and they become the start of `01_simple_1d_model.ipynb`. Keeping it would leave two notebooks for the same step.

## Risks / Trade-offs

- [The notebook test is slow or flaky in CI, for example on kernel start-up] → A generous per-cell timeout. If it proves flaky, mark the test so it can be deselected, which would need a spec change since the spec says the suite runs it.
- [Notebook JSON is awkward to review] → No outputs are committed, and the notebooks are kept short.
- [The notebooks drift from the app's view of the workflow] → Both follow the step names in the `app-navigation` spec, and each notebook title names its step.
- [Plotly cannot display in the test kernel] → Check this first when implementing. If display fails, the notebooks build the figure and call `fig.show()` only outside the test, decided by the renderer setting.

## Open Questions

- Whether the docs should later render these notebooks. It does not affect this change.
