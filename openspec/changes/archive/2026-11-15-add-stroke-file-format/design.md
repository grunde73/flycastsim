# Design

## Context

See proposal.md for the motivation. The current state:

- `fem/_cast1_data.py` holds the stroke drive: `ANGLE_DEG_VIDEO` (12 points,
  interpolated by `phi_handle_rad` with PCHIP, ends held) and a smoothstep
  hand path (`HAND_*`, `hand_xy`, `hand_vel`).
- `simulate_cast1` reads these directly: `cast1_stroke()` for the angle,
  `_cast1_data.hand_vel` for the handle boundary condition (`cast1_bc`), and
  `hand_xy` / `phi_handle_rad` for the output positions and tip deflection.
- `streamlit_app.py` calls `_cast1_data.phi_handle_rad` twice for the
  rigid-rod overlay. `fem_helpers.py` imports `_cast1_data` only for the
  measured reference curves, not for the stroke.
- Tackle components already use "JSON metadata + CSV table, loaded by bundled
  name or path" (`fem/components.py`).

A trial run measured how the Cast #1 result moves when the stroke becomes an
interpolated table with CSV rounding (time 6 decimals, angle 4, position 6):

| Time step | Rows | Chord | Tip deflection | Positions to RSP | Positions, whole cast |
|---|---|---|---|---|---|
| 10 ms | 54 | 0.61 mm | 2.1 mm | 0.84 mm | 52 mm |
| 5 ms | 107 | 0.057 mm | 0.65 mm | 0.10 mm | 5.0 mm |
| 2.5 ms | 213 | 0.011 mm | 0.10 mm | 0.013 mm | 1.3 mm |

The differences grow after RSP, where the line turns over.

## Goals / Non-Goals

**Goals:**
- One representation for every stroke source: a sampled table.
- The stroke code has no knowledge of Cast #1. Cast #1 is only data.
- `simulate_cast1()` with no arguments keeps working, within the tolerances
  in the `cast-stroke` spec.

**Non-Goals:**
- Removing the app's private import. It stays for the AFTM functions.
- Changing `cast1_bc`, `cast_bc`, the solver or the generic `simulate_cast`.
- A resampling or smoothing tool for strokes.

## Decisions

### 1. A sampled table only, no formula-based hand path
The owner accepted a small change in the Cast #1 results. A table fits video,
sensor and hand-drawn sources alike, and a second, parametric representation
would only exist to reproduce one by-eye fit to the last digit.

*Alternative:* allow `"hand_path": {"kind": "smoothstep", ...}` in the JSON.
Rejected: two code paths and a larger format for no physical gain.

### 2. One table with one time column
The CSV has `t_s, angle_deg, hand_x_m, hand_y_m`. The JSON maps logical names
to column names, like the component files:

```json
{
  "name": "Cast #1 stroke",
  "kind": "stroke",
  "description": "...",
  "table_csv": "stroke.csv",
  "columns": {"t": "t_s", "angle": "angle_deg",
              "x": "hand_x_m", "y": "hand_y_m"},
  "source": {"caster": "Mathias Lilleheim", "method": "fitted by eye ...",
             "rod_length_m": 2.74}
}
```

*Alternative:* separate angle and hand tables with their own time bases, which
would keep the 12 digitised angle points untouched. Rejected: sources that
give both give them on the same clock, and one table is simpler to write and
plot. The cost is that the Cast #1 angle is resampled, which is inside the
measured change above.

### 3. Interpolation is fixed, not a file option
Angle and hand position use `scipy.interpolate.PchipInterpolator`, as
`phi_handle_rad` does today, with the time clamped to the table range. The
hand velocity is the first derivative of the hand interpolants and zero
outside the range. There is no `interp` key: a linear option would give a
discontinuous handle velocity, which the solver sees as an impulse.

Interpolants are built once per `Stroke` and cached, since the boundary
condition is evaluated every Newton iteration.

### 4. `Stroke` is a frozen dataclass in a new module `fem/stroke.py`
Fields: `name`, `t`, `angle_deg`, `hand_x`, `hand_y`, `meta` (the remaining
JSON keys). Methods: `angle(t)` in radians, `hand_xy(t)`, `hand_vel(t)`, and
a `t_span` property. Module functions: `load_stroke(source="cast1")`,
`save_stroke(stroke, dest)`, `bundled_stroke_path(name="cast1")`. All four
names are exported from `flycastsim.fem`.

Source resolution follows `_resolve_rig`: a `.json` file, a folder holding
`stroke.json`, or a bundled name. Bundled strokes live in
`src/flycastsim/data/strokes/<name>/`, outside `data/components/`, because a
stroke is not tackle and a rig does not reference one.

`fem/stroke.py` imports only numpy, scipy and the standard library, so the
plotting-free requirement on `flycastsim.fem` holds.

### 5. A 2.5 ms step for the bundled Cast #1 stroke
213 rows from -0.400 s to 0.130 s. Compared with 5 ms, it cuts the change in
the whole-cast positions from 5.0 mm to 1.3 mm for about 5 kB more data. The
spec tolerances are set at roughly four times the measured values at 2.5 ms,
so that platform differences in the solver do not break the test.

The table is generated once from the current `_cast1_data` functions, before
they are removed, by a throwaway script. After that the CSV is the source of
truth. The 12 original angle points and the six hand-path numbers are
recorded in the JSON `source` metadata so the provenance is not lost.

### 6. A frozen reference file proves the tolerance
Once the old stroke code is gone, the test cannot compare against it. Before
any code changes, the default `simulate_cast1()` result is saved to
`tests/unit/data/cast1_reference.npz` (`t`, `X`, `Y`, `chord`, `deflection`;
about 1.6 MB uncompressed, so `np.savez_compressed` and every second time
step if it exceeds 500 kB). `test_simulate_cast1_matches_reference` compares
against it.

### 7. Coarse-sampling warning at 10 ms
`load_stroke` gives a `UserWarning` when the largest time step exceeds 10 ms.
At 10 ms the same smooth stroke already moves the result by 52 mm; at 5 ms by
5 mm. The warning is on loading only. A `Stroke` built in code gets none, so
tests and tools can construct coarse strokes freely.

### 8. `cast1_stroke()` stays
It is public and used by three notebooks. It returns
`load_stroke("cast1").angle` wrapped to return a float, and keeps its unused
`t_start` argument.

### 9. What leaves `_cast1_data`
`ANGLE_DEG_VIDEO`, `phi_handle_rad`, `HAND_*`, `_smoothstep`, `hand_xy` and
`hand_vel` are removed. `RIG`, the AFTM functions, `EVENTS`, `V_RSP`,
`ANGLE_DEG`, `CHORD_M` and `angle_rad_interp` stay. The module is private, so
this is not a public API break. The app's two `phi_handle_rad` calls become
`load_stroke("cast1").angle(t)`.

## Risks / Trade-offs

- [Cast #1 results change] → Accepted by the owner, measured, and bounded by
  a test against a frozen reference.
- [The reference file freezes today's numerics] → A later, intended numerics
  change must regenerate it. The test docstring says how and that it needs a
  proposal.
- [A stroke fitted to one rod length is used with another rod] → Already true
  today. The `source.rod_length_m` metadata records it; nothing enforces it.
- [The 10 ms threshold is a judgment from one stroke] → It only warns. It can
  be tuned later without a format change.
- [`rod_profile_pages.code_version` cache key] → It fingerprints the package's
  `*.py` files only. This change edits those, so cached Cast #1 runs are
  invalidated. A later edit to `stroke.csv` alone would not invalidate them.
  The same gap already exists for the component CSV files, so it is left as
  is and not widened into this change.

## Migration Plan

No user migration: `simulate_cast1()` and `cast1_stroke()` keep their
signatures. Rollback is a revert of the change.
