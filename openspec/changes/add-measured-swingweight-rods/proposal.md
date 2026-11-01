# Proposal

## Why

The PA905 and TCR590 swingweight measurements sit in `assets/` as CSV files that no code reads, so they can't be estimated, checked or used in the app. The files also record overall mass and balance point, which give an independent check on the section data that nothing performs today.

## What Changes

Proposal-required categories: data format, public API and new capability.

- Define the swingweight CSV as a supported format: an overall row followed by sections from tip to butt.
- Add a loader for that format that returns sections ordered butt to tip, the assembled length and the overall measurements.
- Add a consistency check comparing section totals with the measured overall mass and balance point.
- Bundle the PA905 and TCR590 data with the package, moving the CSVs out of `assets/`. This also removes the misspelled `swingwieght` filename.
- Offer both rods as presets in the app's Swingweight view.

Not included: fitted rods and `rod.yaml` stay unchanged, so PA905's empty `rod.yaml` sections and TCR590's disagreement between `rod.yaml` and the CSV remain open.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rod-swingweight`: adds the measurement file format, loading of bundled measured rods, the consistency check and the app presets.

## Impact

- **Code:** `src/flycastsim/rod/data.py`, exports in `src/flycastsim/rod/__init__.py`, and the preset list in `streamlit_app.py`.
- **Data:** new files under `src/flycastsim/data/rods/measured/`. `assets/PA905/swingwieght.csv` and `assets/TCR590/swingweight.csv` move there.
- **Tests and docs:** `tests/unit/test_rod_swingweight.py` and `docs/rod.rst`.
- **Unchanged:** `load_example_rods`, the swingweight estimator, the FEM core and all fit results. No new dependencies.
