# Design

## Context

`load_example_rods` reads `data/rods/example_rods.json`, and every rod there has a published `reference_swingweight_gm2`. `test_example_rods_match_paper_totals` relies on that value for all of them. The app's Swingweight view uses only the make, model, sections, assembled length and reel-seat status of a preset, so it doesn't need the reference value.

Files in `assets/` aren't packaged, so a deployed app can't read them.

## Goals / Non-Goals

**Goals:**
- One source for each measurement, read by both library and app.
- Keep measured rods clearly separate from the paper's validated examples.

**Non-Goals:**
- Changing `rod.yaml`, fit inputs or bundled fitted rods.
- Deciding whether the CSV or `rod.yaml` is right for TCR590.
- Loading CSVs for other rods, or uploading them in the app.

## Decisions

### Move the CSVs into package data

The CSVs move to `data/rods/measured/PA905.csv` and `TCR590.csv`, with a `measured_rods.json` listing each rod's make, model, reel-seat status and file. Copying them would leave two versions to keep in sync. Putting the values into `example_rods.json` would discard the file format and require a made-up reference value. The move also fixes the `swingwieght` filename.

### Separate `load_measured_rods` and `MeasuredRod`

`load_example_rods` stays as it is, and `MeasuredRod` carries measured mass and balance point instead of a reference swingweight. Making the reference optional on `ExampleRod` would weaken the validation test, which needs a published value for each rod. Also exported: `load_swingweight_csv(path)`, for reading a file outside the package, and `check_consistency(rod)`.

### Calculate balance point from the raw sections

`check_consistency` uses the measured butt balance point and the ferrule-corrected distances of paper eqs. 2-5, weighted by section mass. `SectionResult.d` can't be reused, because with the reel-seat correction it holds the inferred blank mass centre rather than the measured value. This is a composite centre-of-mass calculation that isn't in the paper, and the docstring will say so.

### Treat both rods as finished rods

Both have `has_reel_seat: true`, based on their butt section masses (73.6 g and 72.3 g) and the sum matching the overall mass of a complete rod. This is an assumption from the data, and each preset's checkbox can still override it.

### Assume the overall balance point is measured from the butt

The CSV doesn't say so, but PA905's calculated 0.563 m against the measured 0.565 m supports it.

## Risks / Trade-offs

- [The TCR590 preset disagrees with `rod.yaml` and the fitted rod: 102.7 g and 2.75 m against 107.4 g and 2.722 m] → Record the difference in `measured_rods.json` and in the docs. Resolving it is out of scope.
- [Measured presets have no published reference, so their estimates aren't validated] → The tests pin the values only against regressions, and the docs say so.
- [`spec_driven_dev` still has the CSVs at the old paths] → That branch stays unmerged, so nothing needs reconciling.
