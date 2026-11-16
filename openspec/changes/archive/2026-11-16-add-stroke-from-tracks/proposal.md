# Proposal

## Why

Workflow step 4 can load and save a stroke, but there is no way to make one
from a real cast: the only bundled stroke was fitted by eye. Users who film a
cast need a path from points tracked in the video to a `Stroke` that drives the
simulation. The conversion (calibration, angle, smoothing, resampling) is the
part with design risk, and it can be built and tested before any example video
exists.

Proposal-required categories: new capability, data format change (a new track
file format) and public API change.

## What Changes

- Add a track file format: a `tracks.json` metadata file plus a `tracks.csv`
  table holding two tracked points per video frame, `butt` (at or near the rod
  butt) and `rod` (further up the stiff butt section), in pixels or metres.
  The metadata holds the frame rate, the scale, the image orientation, the
  RSP frame and the distance from the rod butt end to the `butt` point.
- Add a public API in `flycastsim.fem`: load and save tracks, convert tracks
  to a `Stroke`, and make synthetic tracks from a known stroke (for tests,
  examples and the study below).
- The conversion calibrates to metres in the stroke frame, takes the rod-butt
  angle from the direction `butt` to `rod`, corrects the hand position to the
  rod butt end, puts RSP at `t = 0` and the hand at the origin there, smooths
  the angle and the hand path with a smoothing spline, and resamples to a
  dense table. It returns the stroke together with the raw samples and the fit
  residuals, and records the capture and smoothing settings in the stroke
  metadata.
- Warn when the track is too coarse to resolve the stop, and when the rod or
  the hand is still moving fast at the start or end of the track.
- Add an example script and a section in the step 4 notebook that extract a
  stroke from tracks.
- Add a documentation page: how to film and track a cast, the track format,
  the method, and its limits.
- Measure how much tracking noise and how low a frame rate the simulated cast
  tolerates, using synthetic tracks made from the bundled Cast #1 stroke, and
  record the result in the documentation.

Not in this change:

- Marking points in the Streamlit app, and any other app page. This is the
  next step and will use the same track format.
- Reading video files, and automatic tracking of the rod in images.
- Dedicated readers for the export files of Tracker or Kinovea. Their exact
  layouts will be pinned down against real export files once example videos
  exist. Until then an export is shaped into the track format by naming its
  columns in `tracks.json`.
- Detecting RSP automatically. The user states the RSP frame or time.
- Strokes from motion sensors.
- Any change to the stroke file format, to `simulate_cast1` or to the bundled
  Cast #1 stroke.

## Capabilities

### New Capabilities
- `stroke-extraction`: the track file format, loading and saving tracks,
  converting tracks to a stroke (calibration, angle, hand path, smoothing,
  resampling), the warnings about coarse or moving tracks, and synthetic
  tracks from a stroke.

### Modified Capabilities
- `example-notebooks`: the requirement "Notebooks state the limits of each
  step" says the step 4 notebook states that a stroke cannot yet be extracted
  from video or sensor data. A stroke can now be made from tracked points, so
  that scenario changes.

## Impact

- New code: `src/flycastsim/fem/tracks.py`, exported from `flycastsim.fem`.
  It uses only NumPy and SciPy, so the FEM core stays plotting-free.
- Tests: new `tests/unit/test_fem_tracks.py`.
- Examples: new `examples/stroke_from_tracks.py` and
  `examples/stroke_extraction_study.py`; `04_casting_parameters.ipynb` gains a
  section.
- Docs: new `docs/stroke_extraction.rst`; updates to `docs/index.rst`,
  `docs/planned.rst`, `README.md`, `CLAUDE.md` and
  `.github/copilot-instructions.md`.
- No new dependencies. `requirements.txt` does not change.
- No change to the solver, so the six exact verification cases and the Cast #1
  reference results are unaffected.
