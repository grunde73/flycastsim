# Tasks

## 1. Freeze the current Cast #1 result

- [x] 1.1 Before changing any package code, save the default `simulate_cast1()` result (`t`, `X`, `Y`, `chord`, `deflection`) to `tests/unit/data/cast1_reference.npz` with `np.savez_compressed`, keeping every second time step if the file exceeds 500 kB. Verify by loading the file and checking that it equals a fresh `simulate_cast1()` run exactly, and that `git status` shows no package file changed.
- [x] 1.2 Add `test_simulate_cast1_matches_reference` to `tests/unit/test_fem_cast.py` with the tolerances from the `cast-stroke` spec (chord 0.05 mm, tip deflection 0.5 mm, positions up to RSP 0.1 mm, whole cast 5 mm) and a docstring saying how to regenerate the file and that doing so needs a proposal. Verify by the test passing against the unchanged code.

## 2. Stroke module and format

- [x] 2.1 Add `src/flycastsim/fem/stroke.py` with the frozen `Stroke` dataclass (`angle`, `hand_xy`, `hand_vel`, `t_span`; PCHIP interpolants built once, ends held, zero velocity outside the table) as in design decisions 3 and 4. Add `tests/unit/test_fem_stroke.py` with `test_stroke_passes_through_samples`, `test_stroke_holds_ends`, `test_hand_velocity_is_position_derivative` and `test_stroke_without_hand_path_is_fixed`. Verify by those tests passing.
- [x] 2.2 Add `load_stroke`, `save_stroke` and `bundled_stroke_path` with the validation and the 10 ms coarse-sampling warning from the spec. Add `test_load_stroke_reads_table_and_metadata`, `test_load_stroke_rejects_invalid` (parametrised over wrong kind, missing `columns`, missing CSV column, one hand column only, one row, non-finite value, non-increasing time), `test_load_stroke_unknown_source`, `test_coarse_stroke_warns` and `test_save_stroke_round_trip`. Verify by those tests passing.
- [x] 2.3 Export `Stroke`, `load_stroke`, `save_stroke` and `bundled_stroke_path` from `flycastsim.fem` and document the file format and conventions in the module docstring. Verify with `uv run lint-imports` passing and `python -c "from flycastsim.fem import Stroke, load_stroke, save_stroke, bundled_stroke_path"` succeeding.

## 3. Bundled Cast #1 stroke

- [x] 3.1 Generate `src/flycastsim/data/strokes/cast1/stroke.json` and `stroke.csv` from the current `_cast1_data` functions with a throwaway script: 213 rows from -0.400 s to 0.130 s at 2.5 ms, time and position to 6 decimals, angle to 4. Put the source, the "fitted by eye" note, the rod length, the 12 original angle points and the six hand-path numbers in the JSON metadata. Add `src/flycastsim/data/strokes/__init__.py` if package resources need it. Verify with `test_bundled_cast1_stroke_loads_clean` (loads by name through package resources, no warning, stated range and step) passing.
- [x] 3.2 Check that the stroke files are in the built wheel. Verify with `uv build --wheel` and `unzip -l dist/*.whl` listing `flycastsim/data/strokes/cast1/stroke.json` and `stroke.csv`, then remove `dist/`.

## 4. Drive Cast #1 from a stroke

- [x] 4.1 Add the `stroke` argument to `simulate_cast1` (bundled name, path or `Stroke`; default `"cast1"`) and use it for the handle angle, the hand velocity in `cast1_bc`, the output hand position and the tip-deflection butt angle. Make `cast1_stroke()` read the bundled stroke. Update the docstrings. Add `test_simulate_cast1_default_stroke_is_bundled`, `test_simulate_cast1_with_custom_stroke` and `test_simulate_cast1_stroke_from_path`. Verify by those tests and `test_simulate_cast1_matches_reference` passing.
- [x] 4.2 Remove `ANGLE_DEG_VIDEO`, `phi_handle_rad`, `HAND_*`, `_smoothstep`, `hand_xy` and `hand_vel` from `_cast1_data.py`, and move `test_cast1_handle_angle_sweeps_q2_to_q1` and `test_cast1_hand_translates` in `test_fem_cast.py` to the bundled stroke. Verify with `grep -rnE "phi_handle_rad|hand_xy|hand_vel|ANGLE_DEG_VIDEO" src tests streamlit_app.py rod_profile_pages.py` finding only `Stroke` methods and their callers, and `uv run pytest tests/unit/test_fem_cast.py` passing.
- [x] 4.3 Replace the two `_cast1_data.phi_handle_rad` calls in `streamlit_app.py` with the public stroke API, keeping the private import only for the AFTM functions. Verify with `uv run pytest tests/unit/test_architecture.py tests/unit/test_app_navigation.py` passing, and by starting the app with `FLYCASTSIM_SHOW_CAST=1` and running the Sample fly cast section with the rigid-rod overlay on.
- [x] 4.4 Run the numerical checks. Verify with `uv run pytest tests/unit/test_fem_verification.py` passing, and record in this task the measured differences against the reference (chord, tip deflection, positions to RSP, whole cast). Result: verification 7 passed; chord 0.011 mm, tip deflection 0.064 mm, positions to RSP 0.010 mm, whole cast 1.34 mm.

## 5. Notebooks and documentation

- [x] 5.1 Update `examples/notebooks/04_casting_parameters.ipynb`: load the bundled stroke with `load_stroke`, plot the angle and the hand path, save a modified copy with `save_stroke` to a temporary folder and load it back, and replace the "cannot yet be loaded" statement with the two limits in the `example-notebooks` delta. Verify with `uv run pytest tests/unit/test_example_notebooks.py` passing.
- [x] 5.2 Update `complete_workflow.ipynb` (and `05_simulate_cast.ipynb` where it shows the stroke) to load the stroke in step 4 and pass it to `simulate_cast1(stroke=...)` in step 5. Verify with `uv run pytest tests/unit/test_example_notebooks.py` passing with outputs cleared.
- [x] 5.3 Document the stroke format and `simulate_cast1(stroke=...)` in `docs/fem.rst` (replacing the references to `_cast1_data` for the stroke), add a short stroke example to `README.md`, and add `load_stroke` and `data/strokes/` to the bundled-data and architecture notes in `.github/copilot-instructions.md`. Verify with `uv run --extra docs --directory docs make html` building without new warnings.

## 6. Integration checks

- [x] 6.1 Run the whole suite and the linters. Verify with `uv run pytest`, `uv run ruff check .`, `uv run lint-imports`, `uv run pre-commit run --all-files` and `openspec validate add-stroke-file-format --strict` all passing, and `git diff --stat requirements.txt` showing no change.

## Workflow follow-up

- Archive the change with `/opsx:archive` after review. This creates the `cast-stroke` spec and updates `example-notebooks`.
