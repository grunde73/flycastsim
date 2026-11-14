# Tasks

## 1. Switch and section list

- [x] 1.1 Add `cast_page_enabled()` to `rod_profile_pages.py`, reading `FLYCASTSIM_SHOW_CAST` and accepting `1`, `true`, `yes` and `on` in any letter case. Verify with `test_cast_switch_values` in a new `tests/unit/test_app_navigation.py`.
- [x] 1.2 Build the section list in `streamlit_app.py` as Introduction (0), Simple 1D model (1), Rod parameters (3), and Sample fly cast (2) only when the switch is on, keeping the ids and the dispatch chain. Verify with `test_default_sections_hide_cast` and `test_cast_switch_shows_cast_section`, and with the existing `test_app_measured_rod_presets` and `test_app_presets_are_unique` passing unchanged.
- [x] 1.3 Check how long the cast page takes to render in `test_cast_switch_shows_cast_section`. If it is slow, reduce the test to the selector contents and page title as described in design.md. Verify by the test finishing within its `default_timeout`.

## 2. Workflow and switch-dependent text

- [x] 2.1 Replace the Introduction's "contains" list in `streamlit_app.py` with the five-step workflow and an availability note per step, and move the Cast #1 demo to the planned list when the switch is off. Verify with `test_intro_presents_workflow` for both switch states.
- [x] 2.2 Make the Stiffness profiles header and the fit result message in `rod_profile_pages.py` mention the cast page only when the switch is on. Verify with `test_hidden_cast_is_not_mentioned`, and by reading the fit result message code for the switch-off case.
- [x] 2.3 Start the app with and without `FLYCASTSIM_SHOW_CAST=1` and look at the Introduction, the Rod parameters views and, with the switch on, the cast page. Verify that the section list and texts match the `app-navigation` spec in both states.

## 3. Documentation

- [x] 3.1 Document the switch in `docs/dev.rst`, and add it to the run commands in `.github/copilot-instructions.md` (`CLAUDE.md` is a symlink to it). Verify that the documented command starts the app with the cast section listed.
- [x] 3.2 Say that "Sample fly cast" is shown only with the switch on where the app's cast demo is described: `README.md`, `docs/index.rst`, `docs/fem.rst` and `docs/rod_profile.rst`. Verify with `uv run --extra docs --directory docs make html` building without new warnings.

## 4. Final checks

- [x] 4.1 Run all checks. Verify with `uv run pytest`, `uv run ruff check .`, `uv run lint-imports` and `openspec validate add-cast-page-switch --strict` passing. Result: all pass except `uv run ruff check .`, which reports 234 errors both with and without this change. This change adds none, and they are fixed separately as the next iteration.

## Workflow follow-up

- Archive the change with `/opsx:archive` once it's implemented, which creates the `app-navigation` spec.
