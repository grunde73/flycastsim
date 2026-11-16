# Design

## Context

See `proposal.md` for the motivation. What shapes the approach:

- A `Stroke` (`fem/stroke.py`) is a table of time, rod-butt angle and hand
  position. It interpolates with PCHIP **through every sample**, so it cannot
  smooth. Any smoothing has to happen before the table is made.
- `simulate_cast1` uses the stroke through `cast1_bc`: the handle angle and the
  hand **velocity** are the boundary conditions. The hand position only shifts
  the output coordinates, and the model has no ground. So the hand origin is a
  free convention, and the quality of an extracted stroke is decided by its
  derivatives.
- The simulation starts with a straight rod at rest, and a stroke holds its end
  values outside its table, where the hand velocity is zero.
- `load_stroke` warns when the largest step in a table is more than 10 ms
  (`COARSE_STEP_S`).
- Strokes and tackle components in `flycastsim.fem` are stored as JSON metadata
  plus a CSV table. `flycastsim.fem` must not import a plotting library.
- No example video or tracker export file is in the repo yet. The owner will
  bring examples later.
- SciPy is at 1.18 in the lock file, so
  `scipy.interpolate.make_smoothing_spline` is available.

## Goals / Non-Goals

**Goals:**

- A conversion from tracked points to a `Stroke` that is fully testable with
  synthetic tracks, with no video in the repo.
- A track format that the later in-app marking can write without change.
- A smoothing setting that a user can judge: the marking accuracy in pixels.
- Honest results: the raw samples, the residuals and the capture settings
  travel with the stroke.

**Non-Goals:**

- Everything under "Not in this change" in the proposal.
- Correcting for a camera that is not square to the casting plane, lens
  distortion or rolling shutter. The filming guide tells the user to avoid
  them.
- Correcting the angle for the bend of the butt section between the two
  points.

## Decisions

### 1. A new module `flycastsim/fem/tracks.py`

The module sits next to `fem/stroke.py` and is exported from `flycastsim.fem`.
It imports only NumPy, SciPy and `fem/stroke.py`.

Public names:

| Name | Role |
|---|---|
| `StrokeTracks` | Frozen dataclass: name, times, `butt` and `rod` positions, extra points, units, scale, orientation, RSP time, `butt_offset_m`, tracking noise, metadata |
| `load_tracks`, `save_tracks` | Read and write `tracks.json` + `tracks.csv` |
| `stroke_from_tracks` | The conversion; returns a `StrokeExtraction` |
| `StrokeExtraction` | Frozen dataclass: the `Stroke`, the raw samples, the RMS deviations |
| `tracks_from_stroke` | Synthetic tracks from a stroke |

Alternative considered: a new subpackage (`flycastsim.cast` or
`flycastsim.video`). Rejected for now: there is one module of code, and the
stroke it produces lives in `flycastsim.fem`. If image tracking is added later
it will need its own home, because it brings image dependencies that the FEM
core should not carry; the track format is the boundary between the two.

### 2. Track files are JSON + CSV, like stroke files

`tracks.json`:

```json
{
  "name": "My cast",
  "kind": "stroke_tracks",
  "table_csv": "tracks.csv",
  "columns": {"frame": "frame",
              "butt_x": "butt_x", "butt_y": "butt_y",
              "rod_x": "rod_x", "rod_y": "rod_y"},
  "fps": 240,
  "units": "px",
  "scale": {"length_m": 2.74, "from_px": [412, 655], "to_px": [1310, 201]},
  "y_axis": "down",
  "casting_direction": "right",
  "rsp": {"frame": 152},
  "butt_offset_m": 0.10,
  "tracking_noise": 1.5
}
```

The `columns` mapping lets a tracker export be used by naming its columns,
without renaming them in the CSV. The CSV reader is the one in `fem/stroke.py`
(header row, `#` comment lines skipped), extended to accept empty cells.

Alternative considered: a YAML file like `rod.yaml`. Rejected: the tracks feed
a stroke, and strokes and components in `flycastsim.fem` are JSON + CSV; the
rod measurement is YAML because it is edited by hand at length.

### 3. Two points, and a butt offset

The angle is `atan2` of the direction `butt` to `rod`, after the table has been
brought into the stroke frame (scale, flip `y` when it grows down, mirror `x`
when the cast goes left). The angle is unwrapped over time.

The model rotates the rod about its butt end. A user will often track the hand
or a tape mark instead. A 0.10 m error through an 85 degree sweep is about
0.14 m of false hand travel, so the raw hand sample is the `butt` point moved
back by `butt_offset_m` along the raw direction of that row.

Alternative considered: track only the `butt` point and an angle measured with
the tracker's protractor. Rejected: two points are what every tracker exports,
and they also suit the later in-app marking.

### 4. Smoothing spline, with the strength from the tracking noise

The angle and the two hand coordinates are each fitted with a cubic smoothing
spline over time (`make_smoothing_spline`). It handles uneven sampling and
skipped rows, and gives smooth first and second derivatives.

- **Noise stated** (`noise` argument, else `tracking_noise` in the file, in
  table units, as the standard deviation per coordinate): the smoothing
  parameter is the largest one for which the residual equals the noise
  (Reinsch's criterion), found by a bracketed root search on its logarithm.
  For the hand the target is the noise times the scale. For the angle the
  noise of row `i` is `sqrt(2) * noise / d_i`, with `d_i` the distance between
  the two points, used as weights. If the search hits the upper end of the
  bracket, the data are smoother than the stated noise and the upper end is
  used; at the lower end the spline interpolates.
  Lowering the target by the fit's degrees of freedom (estimated with random
  probes) was tried and dropped: on synthetic Cast #1 tracks it did not
  improve the position error and made the velocity error worse.
- **No noise stated**: generalised cross-validation, which is what
  `make_smoothing_spline` does when no parameter is given, with the same
  weights for the angle.
- **Smoothing off**: the raw samples are the stroke table.

The hand RMS deviation in the result and in the spec is per coordinate:
`sqrt(mean((dx**2 + dy**2) / 2))`.

Sources to cite in the module docstring: Reinsch, *Smoothing by spline
functions*, Numer. Math. 10 (1967); Craven and Wahba, *Smoothing noisy data
with spline functions*, Numer. Math. 31 (1979); Woltring, *A Fortran package
for generalized, cross-validatory spline smoothing and differentiation*,
Adv. Eng. Software 8 (1986), which is the standard reference for this method
in movement analysis.

Alternatives considered:

- A zero-phase low-pass filter with a cut-off frequency, the convention in
  biomechanics. Rejected: it needs even sampling, behaves poorly at the ends of
  a short track, and no cut-off is established for fly casting.
- Savitzky-Golay. Rejected for the same sampling and end problems.
- Smoothing the two point tracks and then taking the angle. Rejected: the
  angle is the quantity that drives the simulation, and its noise depends on
  the point distance, which the weights handle directly.

### 5. Resampling and origin

With smoothing on, the splines are sampled at `t = k * dt` for the integers
`k` that fall inside the track's time range (`dt` = 2.5 ms by default, the
step of the bundled stroke). So `t = 0` is always a table time, the table
never extrapolates, and it may start up to one step after the first track
time. The hand position at `t = 0` is subtracted from the hand path.

The dense table means `load_stroke` will not warn for a stroke filmed at
30 frames per second. The frame rate is therefore checked at conversion
(decision 6) and recorded in the stroke metadata.

### 6. Warnings

Both are `UserWarning`s from `stroke_from_tracks`, and the stroke is still
returned:

- median track step above `COARSE_STEP_S` (10 ms);
- mean angular speed or mean hand speed over the first or last 5 % of the
  track's duration (at least three track steps) above 20 % of its peak over
  the track, evaluated on the fitted curves.

The mean over a short window is used because the end derivative of a fitted
curve is too noisy: judged at the end point alone, the warning fired on most
noisy synthetic tracks. The bundled Cast #1 stroke also begins with its
largest hand acceleration at the first table time, which no smooth curve
follows, so synthetic tracks need a filmed pause before and after the stroke
(decision 8), as a real clip does. With a 0.1 s pause, 1350 noisy conversions
(30 to 500 frames per second, 0.5 to 2 pixels, all three smoothing modes) gave
7 false warnings, all at 2 pixels of noise.

### 7. Stroke metadata

The extracted stroke's `meta` gets a `source` entry:

```json
{"source": {"method": "tracks", "tracks": "My cast", "samples": 187,
            "median_step_s": 0.004167,
            "smoothing": "smoothing spline, Reinsch criterion",
            "tracking_noise": 1.5, "tracking_noise_units": "px",
            "rms_angle_deg": 0.31, "rms_hand_m": 0.0042,
            "m_per_unit": 0.00305, "butt_offset_m": 0.10}}
```

A `source` entry already in the tracks' metadata is kept under
`source.tracks_source`.

### 8. Synthetic tracks

`tracks_from_stroke` places the `butt` point at the hand position plus
`butt_offset_m` along the rod direction, and the `rod` point a given distance
further along the same straight line, then applies the inverse of the
calibration and orientation and adds Gaussian noise from a seeded generator.
A `pause_s` argument extends the track before and after the stroke, where the
stroke holds its end values.
It is the test fixture, the notebook's data and the input of the study.

### 9. The noise and frame-rate study

`examples/stroke_extraction_study.py` makes tracks from the bundled Cast #1
stroke at 500, 240, 120, 60 and 30 frames per second with 0, 0.5, 1 and 2
pixels of noise at 3 mm per pixel, several seeds each, extracts a stroke with
the noise stated, runs `simulate_cast1` with it, and compares the rod chord
length and the tip deflection with the default run. The table of results goes
into `docs/stroke_extraction.rst`.

Result (task 4.2, synthetic tracks, so optimistic): tracking noise matters
more than frame rate. With 1 pixel of noise at 3 mm per pixel and 240 frames
per second, the extracted stroke is within 0.25 degrees and 1.8 mm RMS, but its
peak angular speed is 12 % low and the simulated chord differs by about 20 mm
(of 166 mm of shortening) and the tip deflection by about 77 mm (of 1676 mm).
Without noise the frame rate alone costs under 3 mm of chord down to 60 frames
per second and 10 mm at 30. Stating the noise and automatic smoothing give
similar errors in the simulated rod; automatic smoothing clips the peak
angular speed less (6 % against 12 %) but lets more noise through. Halving the
pixel size or doubling the distance between the two points each cut the chord
error from 20 mm to about 13 mm, so the angle noise dominates. The bundled
stroke has kinks in its angular velocity (it is a PCHIP curve through 12
points), which any smoother clips, so the peak-speed loss on a real stroke is
probably smaller. Follow-up worth considering: a smoothing strength that
varies over the stroke.

The study describes; it is not a pass/fail gate. If it shows that a number in
the spec is wrong (the 10 ms and 20 % limits, the recovery tolerances) or that
the default smoothing flattens the stop, the change artifacts are updated
before the change is finished.

## Risks / Trade-offs

- [The recovery tolerances in the spec (0.2 deg and 1 mm without noise,
  0.5 deg and 3 mm RMS with 1 px of noise) are estimates; nothing has been run
  yet] → They are checked as soon as the conversion exists (task group 3). If
  one cannot be met, stop and update the spec with the measured value and the
  reason, and do not loosen it silently.
- [A single smoothing strength rounds off the stop, the most important
  feature of the stroke] → The result carries the raw samples and residuals,
  the notebook plots raw against smoothed, and the study measures the effect
  on the simulated cast. A time-varying strength is a follow-up if the study
  calls for it.
- [Cross-validation under-smooths when the tracking errors of neighbouring
  frames are correlated, as with an automatic tracker] → The stated-noise path
  is the documented recommendation; the automatic path is the fallback.
- [The rod bends between the two points under load, which biases the angle]
  → The filming guide gives the trade-off (far apart for less pixel noise,
  close for less bend) and recommends 0.3 to 0.5 m; the bias is listed as a
  limit in the docs.
- [The camera view is not square to the casting plane] → Stated as a
  requirement in the filming guide and as a limit in the docs; not corrected.
- [Real tracker exports may not fit the column mapping, for example with
  several header lines or a decimal comma] → Out of scope until real export
  files exist; the docs say the table must be a plain comma-separated file.
- [Synthetic tracks assume a straight rod and independent Gaussian noise, so
  the study is optimistic] → Said in the docs next to the results; real
  footage is the follow-up check.

## Open Questions

- The exact export layouts of Tracker and Kinovea, and whether dedicated
  readers are worth having. Answered when example videos and their exports are
  in hand; it does not change this change.
- Whether RSP should later be found automatically, for example from a tracked
  tip. It would add to the track format without changing it.
