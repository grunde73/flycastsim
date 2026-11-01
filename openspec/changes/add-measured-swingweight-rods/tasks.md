# Tasks

## 1. Measurement files and loader

- [ ] 1.1 Move the two CSVs to `src/flycastsim/data/rods/measured/PA905.csv` and `TCR590.csv` with `git mv`, and add `measured_rods.json` including a note on the TCR590 `rod.yaml` disagreement. Verify with `git status` showing renames and `test_wheel_ships_bundled_data` passing.
- [ ] 1.2 Add `MeasuredRod`, `load_swingweight_csv` and `load_measured_rods` to `rod/data.py`, cite the source in docstrings, and export them from `rod/__init__.py`. Verify with `test_measurement_file_rows_and_units`, `test_measurement_file_bad_header_raises`, `test_measurement_file_without_sections_raises`, `test_measured_rods_load_and_estimate` and `test_measured_rods_estimates`.
- [ ] 1.3 Confirm the worked examples are untouched. Verify with `test_example_rods_match_paper_totals` passing unchanged.

## 2. Consistency check

- [ ] 2.1 Add `check_consistency`, noting in its docstring that the composite balance point isn't from the paper. Verify with `test_consistency_check_values`.

## 3. App presets

- [ ] 3.1 Add the measured rods to the preset list in `streamlit_app.py` and update its help text, using only public imports. Verify with `test_app_measured_rod_presets` (Streamlit `AppTest`) and `test_app_imports_only_public_api`.

## 4. Documentation and final checks

- [ ] 4.1 Document the file format, loader, consistency check and TCR590 disagreement in `docs/rod.rst`. Verify with `uv run --extra docs --directory docs make html` building without new warnings.
- [ ] 4.2 Run all checks. Verify with `uv run pytest`, `uv run ruff check .`, `uv run lint-imports` and `openspec validate add-measured-swingweight-rods --strict` passing.

## Workflow follow-up

- Archive the change with `/opsx:archive` once it's implemented, which merges these requirements into the `rod-swingweight` spec.
