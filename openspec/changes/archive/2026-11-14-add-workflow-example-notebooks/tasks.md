# Tasks

## 1. Tooling and test harness

- [x] 1.1 Add `ipykernel` and `nbclient` to the `dev` dependency group and update `uv.lock`. Do not add them to the `app` group. Verify with `uv sync` succeeding, `scripts/check_requirements.sh` passing, and `git diff --stat requirements.txt` showing no change.
- [x] 1.2 Add `tests/unit/test_example_notebooks.py` with `test_notebook_executes`, `test_notebook_imports_only_public_api` and `test_notebook_has_no_outputs`, each collecting `examples/notebooks/*.ipynb`, plus `test_step_notebooks_exist`, `test_complete_workflow_covers_steps` and `test_notebook_tools_not_in_app_requirements`. Verify by the tests failing for the expected reason while the folder is empty or a notebook is missing.
- [x] 1.3 Check that a Plotly figure displays in the test kernel, using a throwaway notebook. Verify by the throwaway notebook executing under `nbclient` without an error, then delete it.

## 2. Step notebooks

- [x] 2.1 Write `examples/notebooks/01_simple_1d_model.ipynb` from the content of `flysim_examples.ipynb`, with the import fixed to `flycastsim`, and remove `flysim_examples.ipynb`. Verify with `test_notebook_executes` passing for it.
- [x] 2.2 Write `02_rod_characteristics.ipynb`: swingweight from sections, measured rods and the consistency check, fitted profiles, and the fit cell guarded by `RUN_FIT = False` with a note on run time. Verify with `test_notebook_executes` passing for it, and by running the fit cell once by hand with `RUN_FIT = True` and the quick preset. Result: the quick fit of XP590 took about 10 seconds.
- [x] 2.3 Write `03_line_and_leader.ipynb`: load the line and leader components, scale the line to an AFTM weight, plot the mass and diameter profiles, and assemble the rig. State that one line and one leader are bundled. Verify with `test_notebook_executes` passing for it.
- [x] 2.4 Write `04_casting_parameters.ipynb`: plot the idealised stroke and the Cast #1 stroke as rod-butt angle over time, and state that a stroke cannot yet be loaded from a file or passed to the Cast #1 simulation. Verify with `test_notebook_executes` passing for it.
- [x] 2.5 Write `05_simulate_cast.ipynb`: run the generic cast and Cast #1, and show snapshots, chord length, tip deflection and speeds. Verify with `test_notebook_executes` passing for it.

## 3. Complete workflow notebook

- [x] 3.1 Write `complete_workflow.ipynb` with one section per step 2 to 5: pick a fitted rod, pick a line weight, show the stroke, simulate Cast #1 with those inputs and compare the tabulated and fitted rods. Verify with `test_notebook_executes` and `test_complete_workflow_covers_steps` passing.
- [x] 3.2 Clear outputs and execution counts in all six notebooks and set the kernel to `python3`. Verify with `test_notebook_has_no_outputs` and `test_notebook_imports_only_public_api` passing for all six.

## 4. Documentation

- [x] 4.1 Replace the references to `flysim_examples.ipynb` in `README.md`, `docs/index.rst` and `docs/dev.rst` with the new notebooks and how to open them, and mention the notebook test in `.github/copilot-instructions.md`. Verify with `grep -r flysim_examples` finding no references outside `openspec/`, and `uv run --extra docs --directory docs make html` building without new warnings.

## 5. Final checks

- [x] 5.1 Run all checks. Verify with `uv run pytest`, `uv run ruff check .`, `uv run lint-imports`, `uv run pre-commit run --all-files` and `openspec validate add-workflow-example-notebooks --strict` passing, and note how much time the notebook test adds to the suite. Result: all pass. The notebook tests add about 20 seconds (the suite went from about 43 to about 64 seconds), mostly from the Cast #1 runs in `05_simulate_cast` and `complete_workflow`.

## Workflow follow-up

- Archive the change with `/opsx:archive` once it's implemented, which creates the `example-notebooks` spec.
