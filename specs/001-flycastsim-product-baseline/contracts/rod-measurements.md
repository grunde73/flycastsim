# Rod Measurement and Fitted-Rod Contract

## Measurement directory

A rod measurement directory is rooted at `rod.yaml` with schema identifier
`flycastsim.rod.measurement/1`. It records SI values unless keys explicitly
identify grams, degrees, or pixels. Relative image and CSV paths resolve from
the measurement directory. Unknown observations may be `null`.

### Sections

- `rod`: id, make/model, line weight, assembled length, section data, and
  ferrule overlap where known. Each section has a name, mass, length, and
  balance point from the thick end.
- `mount`: clamp arc position and clamp/butt angle.
- `calibration`: image scale/orientation, clamp pixel position, trace start,
  and optional marker positions.
- `static_bend`: frame/image paths, load point and load assumptions, trace
  direction, and excluded frame indices.
- `ccs` (optional): CCS load, deflection fraction, free length, and action
  angle.
- `frequency_test` (optional): CSV path and tip-mass/load-point/clamp settings.

Frequency CSV data uses tip mass in grams and frequency in hertz. Frame
ordering and image traces must be reproducible from the measurement
description and its files.

## Archive and fitting behavior

- Accept only supported rod archives and safely extract them; reject malformed
  archives or invalid measurement descriptions with an explicit user-visible
  error.
- Provide a trace preview and allow frame exclusion before fitting.
- Support the named quick and full fit presets.
- Fit stiffness and mass profiles together with the available measurement,
  calibration, load, and mount parameters.
- Do not represent a fit without absolute scale information as a meaningful
  absolute profile.
- Export a fitted rod with provenance, units, profiles, fit settings, and
  diagnostic summary.

## Fitted-rod bundle

The fitted-rod folder consists of `rod.json`, `rod.csv`, and
`fit_summary.json`. It can be loaded as a rod component and profiled through
the package API. The app offers it as a downloadable zip and registers a
session copy for the current app session.

## Runtime cache and retention

Uploaded source archives and fit artifacts are cached in shared temporary
server storage using content and fit settings to reuse matching work.
Session-specific fitted rods are separately copied into session storage.
There is no fixed retention promise for shared temporary cache files.
