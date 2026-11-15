# Tasks

## 1. Public AFTM module

- [x] 1.1 Before changing any code, record the head masses for weights 1 to 12 and 4.5 from `_cast1_data.line_head_mass_grams` in `test_fem_aftm.py` as expected values. Verify by printing them from the unchanged code and checking that `git status` shows no package file changed.
- [x] 1.2 Add `src/flycastsim/fem/aftm.py` with the table, the two functions and the range check from design decision 4, with a module docstring citing the AFTM (AFFTA) standard. Export the five names from `flycastsim.fem`. Add `tests/unit/test_fem_aftm.py` with `test_aftm_table_values`, `test_head_mass_whole_weights`, `test_head_mass_interpolates`, `test_line_mass_per_length` and `test_out_of_range_weight_rejected`. Verify by those tests passing and `uv run lint-imports` passing.

## 2. Move the callers

- [x] 2.1 Make `fem/components.py` import from `aftm`, and remove the AFTM names from `_cast1_data.py`. Move `test_cast1_line_mass_per_length` out of `test_fem_cast.py` (its checks are covered by `test_fem_aftm.py`), and add `test_component_rejects_out_of_range_weight`. Verify with `grep -rnE "AFTM_HEAD|GRAIN_KG|line_head_mass_grams|line_mass_per_length" src tests streamlit_app.py` finding no `_cast1_data` use, and `uv run pytest tests/unit/test_fem_aftm.py tests/unit/test_fem_cast.py tests/unit/test_fem_multidomain.py` passing.
- [x] 2.2 Switch `streamlit_app.py` to the public functions and drop `_cast1_data` from its imports. Remove `KNOWN_PRIVATE_IMPORTS` from `test_architecture.py` and assert that the app imports no private names. Verify with `uv run pytest tests/unit/test_architecture.py tests/unit/test_app_navigation.py` passing, and by running the Sample fly cast section with `FLYCASTSIM_SHOW_CAST=1` under `AppTest` and checking that the sidebar caption still shows 9.1 g per 30 ft head for a 5-wt.
- [x] 2.3 Run the numerical checks. Verify with `uv run pytest tests/unit/test_fem_verification.py` and `tests/unit/test_fem_cast.py::test_simulate_cast1_matches_reference` passing.

## 3. Notebook and documentation

- [x] 3.1 Add a cell to `examples/notebooks/03_line_and_leader.ipynb` that prints the AFTM table (weight, grains, head mass in grams, mass per length in g/m) from the public API, before the "Scale the line to an AFTM weight" section. Verify with `uv run pytest tests/unit/test_example_notebooks.py` passing with outputs cleared.
- [x] 3.2 Document `flycastsim.fem.aftm` in `docs/fem.rst` where the AFTM line weight is described, and remove any statement that the app has a private-import exception from `.github/copilot-instructions.md` and `docs/`. Verify with `grep -rn "_cast1_data" .github docs/*.rst README.md` finding no app exception, and `uv run --extra docs --directory docs make html` giving no new warnings.

## 4. Integration checks

- [x] 4.1 Run the whole suite and the linters. Verify with `uv run pytest`, `uv run ruff check .`, `uv run lint-imports`, `uv run pre-commit run --all-files` and `openspec validate add-public-aftm-line-table --strict` all passing, and `git diff --stat requirements.txt` showing no change.

## Workflow follow-up

- Archive the change with `/opsx:archive` after review. This creates the `aftm-line-standard` spec and updates `architecture`.
