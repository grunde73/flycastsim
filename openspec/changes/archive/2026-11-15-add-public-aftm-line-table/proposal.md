# Proposal

## Why

The AFTM fly-line weight standard (the nominal head mass for each line
weight) is part of workflow step 3, but it lives in the private module
`flycastsim.fem._cast1_data` next to the Cast #1 reference data. The app
imports that private module only for these two functions, which is the last
known exception in the architecture requirement "App uses the public API".
Notebooks and users cannot use the table without a private import either.

Proposal-required categories: public API change, new capability, and
changing an architecture requirement (the known exception is removed).

## What Changes

- Add a public module `flycastsim.fem.aftm` with the AFTM table and its
  functions, exported from `flycastsim.fem`: `AFTM_HEAD_GRAINS`,
  `AFTM_HEAD_LENGTH_M`, `GRAIN_KG`, `line_head_mass_grams` and
  `line_mass_per_length`.
- Remove these names from `_cast1_data`, which keeps only Cast #1 rig and
  reference data. The component loader uses the public module.
- Line weights outside the table (below 1 or above 12) and non-finite
  weights raise `ValueError`. Today they are silently clamped to the
  nearest end of the table. Weights inside the range give the same values
  as today, so no Cast #1 or component result changes.
- The app reads the line masses from the public API and no longer imports
  any private `flycastsim` name.
- The architecture requirement "App uses the public API" drops its known
  exception: the app files import no private names at all.
- The step 3 notebook shows the AFTM table.

Not in this change:

- The tolerance bands of the AFTM standard. Only the nominal masses are
  provided, as today.
- Moving the Cast #1 rig metadata and reference curves (`RIG`, `EVENTS`,
  `CHORD_M`, ...) out of `_cast1_data`. They are used inside the package
  only, which the architecture requirement allows.

## Capabilities

### New Capabilities
- `aftm-line-standard`: the AFTM fly-line weight table, the head mass and
  line mass per length for a line weight, and how out-of-range weights are
  handled.

### Modified Capabilities
- `architecture`: the requirement "App uses the public API" no longer has a
  known exception.

## Impact

- New code: `src/flycastsim/fem/aftm.py`, exported from `flycastsim.fem`.
- Changed code: `fem/_cast1_data.py` (AFTM names removed),
  `fem/components.py` (imports from `aftm`), `streamlit_app.py` (public
  import, private import removed).
- Tests: new `tests/unit/test_fem_aftm.py`; `test_cast1_line_mass_per_length`
  in `tests/unit/test_fem_cast.py` moves to it; `tests/unit/test_architecture.py`
  loses `KNOWN_PRIVATE_IMPORTS`.
- Notebook: `examples/notebooks/03_line_and_leader.ipynb`.
- Docs: `docs/fem.rst`. No new dependencies; `requirements.txt` does not
  change.
