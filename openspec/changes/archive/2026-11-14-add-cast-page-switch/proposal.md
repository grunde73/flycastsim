# Proposal

## Why

The app should follow an explicit five-step workflow: (1) the standalone simple 1-D model, (2) rod characteristics, (3) line and leader characteristics, (4) casting parameters (the caster's motion), and (5) simulating a fly cast from 2, 3 and 4. Today steps 3, 4 and 5 are bundled into the single "Sample fly cast" page, whose stroke is still fitted by eye, so the published app presents an unfinished cast simulation alongside the finished rod tools.

## What Changes

Proposal-required category: new capability. The app's sections have no capability spec, and this change adds the first one. Hiding a page would not need a proposal on its own.

- Add a switch, off by default, that controls whether the "Sample fly cast" section is offered. The published app runs with it off, and a developer turns it on locally. The page code stays in place.
- List the sections in workflow order, so "Rod parameters" comes before "Sample fly cast" when the latter is shown.
- Present the five-step workflow on the Introduction page, marking which steps the app offers.
- Stop the visible app from pointing at a hidden section: the mentions of using fitted rods in "Sample fly cast" (Introduction, Stiffness profiles, the fit result message) follow the switch.
- Document the switch in the contributor guide, and qualify the claims about the cast demo in the README and docs.

Not included:

- Separate pages for line and leader (step 3) or casting parameters (step 4). The line weight stays in the cast page's sidebar and is hidden with it.
- A stroke file format, which step 4 needs before step 5 can run from pre-calculated parameters. That is a data format change for a later proposal.
- Any change to the `flycastsim` package, the Cast #1 simulation or its results.

## Capabilities

### New Capabilities

- `app-navigation`: which sections the Streamlit app offers, their order, the switch for the cast section, and the workflow shown on the Introduction page.

### Modified Capabilities

None.

## Impact

- `streamlit_app.py`: section list, Introduction text, and the cast page's entry in the selector.
- `rod_profile_pages.py`: the two texts that mention the cast page, and the function that reads the switch.
- `tests/unit/test_app_navigation.py`: new app tests. The existing swingweight app tests select "Rod parameters" by its `("Rod parameters", 3)` value, which stays unchanged.
- `docs/dev.rst`, `docs/index.rst`, `docs/fem.rst`, `docs/rod_profile.rst`, `README.md` and `.github/copilot-instructions.md` (which `CLAUDE.md` links to): the switch and the qualified claims.
- No package code, public API, data format or dependency changes. Users of the published app lose access to the Cast #1 demo until the switch is turned on for that deployment.
