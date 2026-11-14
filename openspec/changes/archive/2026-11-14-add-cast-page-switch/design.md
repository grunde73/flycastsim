# Design

## Context

See proposal.md for the motivation. The facts that shape the approach:

- `streamlit_app.py` picks a section with one sidebar selectbox whose options are `(label, id)` tuples, and dispatches on the id in an `if`/`elif` chain. The cast page is the `id == 2` branch, about 250 lines, and builds its own sidebar.
- The existing app tests select `("Rod parameters", 3)` by value.
- Three texts point at the cast page: the Introduction list in `streamlit_app.py`, and the Stiffness profiles header and the fit result message in `rod_profile_pages.py`.
- `streamlit_app.py` already imports helpers from `rod_profile_pages.py`, not the other way round.
- The app files must stay a thin presentation layer and import only public `flycastsim` names. `flycastsim.fem._cast1_data` is a known exception that the cast page uses.

## Goals / Non-Goals

**Goals:**

- One switch decides whether the cast section exists in the running app.
- The hidden page stays linted and tested, so it does not rot.
- The published app needs no configuration to hide the page.

**Non-Goals:**

- Splitting the cast page into line and leader, casting parameters and simulation pages.
- Removing the `_cast1_data` exception.
- Per-user or per-session access control. The switch is per deployment.

## Decisions

### Environment variable, off by default

The switch is the environment variable `FLYCASTSIM_SHOW_CAST`. Unset means off, so Streamlit Cloud hides the page with no setup, and a developer runs `FLYCASTSIM_SHOW_CAST=1 uv run streamlit run streamlit_app.py`. Tests set it with `monkeypatch.setenv`.

Alternatives considered:

- A Streamlit secret. It can be flipped in the Streamlit Cloud dashboard, but needs a local `.streamlit/secrets.toml` and is awkward in `AppTest`. Streamlit Cloud also exposes root-level secrets as environment variables, so the environment variable can be turned on there the same way if that is ever wanted.
- A URL query parameter. Anyone who knows it can reach the page, which defeats hiding it.
- Commenting out the page. The code would no longer be linted or tested.
- Removing only the selector entry. The page could not be viewed without editing the file.

### The switch is read in one function in `rod_profile_pages.py`

A function `cast_page_enabled()` reads and parses the variable. It lives in `rod_profile_pages.py` because both app files need it and the import direction already runs from `streamlit_app.py` to `rod_profile_pages.py`. It is presentation logic, so it stays out of the `flycastsim` package. It reads the environment on each call, since a Streamlit rerun is cheap and the tests change the variable between runs.

### Section ids are kept, the list order changes

The section list is built as Introduction (0), Simple 1D model (1), Rod parameters (3), and Sample fly cast (2) appended only when the switch is on. Keeping the ids leaves the dispatch chain and the existing tests untouched. With the switch off the `id == 2` branch is unreachable, so the page and its sidebar never run.

### Switch-dependent text is chosen in place

Each of the three texts gets a short conditional on `cast_page_enabled()`. The Introduction's "contains" list is replaced by the five-step workflow with an availability note per step, and the Cast #1 demo moves to the "planned" side when the switch is off. No templating layer is added for three texts.

### Tests drive the real app

`tests/unit/test_app_navigation.py` uses `AppTest.from_file` on `streamlit_app.py`, as the swingweight app tests do. The switch-on test selects the cast section and checks it renders without an exception. It does not click "Run simulation", so it does not run a Cast #1 simulation.

## Risks / Trade-offs

- [The published app loses the Cast #1 demo, which the README and docs advertise] → The README and docs say the section is shown only with the switch on, and docs/dev.rst documents the switch.
- [The hidden page breaks unnoticed] → The switch-on test renders it on every test run, and ruff still checks the code.
- [The cast page renders slowly in the test, for example when it loads the video frames] → Check the timing when writing the test. If it is slow, the test asserts the selector contents and the page title only, with a longer `default_timeout`.
- [A text pointing at the hidden section is missed] → `test_hidden_cast_is_not_mentioned` checks the pages it can reach. The fit result message relies on review.

## Migration Plan

Deploying is a normal push: the variable is unset on Streamlit Cloud, so the section disappears. To roll back, set `FLYCASTSIM_SHOW_CAST=1` for the deployment, or revert the commit.
