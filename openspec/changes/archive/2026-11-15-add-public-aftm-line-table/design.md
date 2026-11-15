# Design

## Context

See proposal.md for the motivation. The AFTM names live in
`fem/_cast1_data.py` (lines 44-90). Inside the package they are used by
`fem/components.py` (`_aftm_mass_scale` and the default
`aftm_head_length_m`). Outside it they are used by `streamlit_app.py` (the
sidebar caption with the head and line mass) and by
`tests/unit/test_fem_cast.py::test_cast1_line_mass_per_length`. Out-of-range
weights are clamped today by `np.interp`: a weight of 0 or 13 gives the 1-wt
or 12-wt mass.

## Goals / Non-Goals

**Goals:**
- One public home for the standard, with no Cast #1 data in it.
- No change in any result for weights 1 to 12.

**Non-Goals:**
- Renaming the functions, or adding the standard's tolerance bands.
- Moving the other `_cast1_data` contents.

## Decisions

### 1. A new module `flycastsim.fem.aftm`
It is a fly-line standard used by the component loader, so it belongs in
`fem` next to `components.py`, which imports it. It has no dependencies
beyond numpy, so the plotting-free requirement on `fem` holds.

*Alternative:* put the names in `components.py`. Rejected: the module is
about loading files; the standard is reference data with its own tests.

*Alternative:* a top-level `flycastsim.line` package. Rejected for now: there
is no other line code to put there, and `fem` is where the components are.

### 2. Keep the existing names
`AFTM_HEAD_GRAINS`, `AFTM_HEAD_LENGTH_M`, `GRAIN_KG`, `line_head_mass_grams`
and `line_mass_per_length` keep their names, so callers only change the
import. The module name `aftm` gives the context the function names lack.

### 3. No compatibility aliases in `_cast1_data`
`_cast1_data` is private, so no deprecation period is owed. Keeping aliases
would let the app or tests drift back to the private import.

### 4. A range check instead of clamping
A shared `_check_weight` rejects weights below 1, above 12 and non-finite
values with a `ValueError` naming the range. Clamping hides a mistake: a user
asking for a 14-wt line silently gets a 12-wt line. Both public functions call
it, and so does the component loader, because `_aftm_mass_scale` goes through
`line_head_mass_grams`.

The interpolation stays as it is (`np.interp` over the table), so values in
range are bit-identical to today.

### 5. The app imports from `flycastsim.fem`
The two calls become `line_mass_per_length(...)` and
`line_head_mass_grams(...)` imported from `flycastsim.fem`, and
`_cast1_data` is dropped from the import list. With no private import left,
`KNOWN_PRIVATE_IMPORTS` in `test_architecture.py` is removed and the test
asserts that the set of private imports is empty.

## Risks / Trade-offs

- [A user rig with an AFTM weight outside 1 to 12 now fails to load] → It
  was silently wrong before. The error names the valid range.
- [The generic names `line_head_mass_grams` and `line_mass_per_length` are
  exported at the top of `flycastsim.fem`] → Their docstrings name the AFTM
  standard. Renaming would cost more churn than it saves.
