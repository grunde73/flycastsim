# Data Model: flycastsim Product Baseline

This model describes the product's runtime and file-based data structures. It
does not introduce a database or persistent account model.

## Simulation Configuration

Represents the inputs to a user-selected model run.

### 1-D oscillator inputs

- Spring stiffness, in N/m.
- Brick mass, in kg internally and grams in the app.
- Car velocity profile controls: maximum speed, turn time, and stop time.
- Initial position/velocity and simulation duration.
- Display choices: selected output columns, reference comparison, event
  markers, and animation.

### Cast #1 inputs

- AFTM line weight (3–8).
- Rod selection: tabulated, packaged fitted rod, or session-fitted rod.
- Rod stiffness scale.
- Grid node count (101, 121, or 141).
- Air-drag and material-damping flags.
- Rod diameter mode for fitted rods.
- Display and measurement choices, including line-speed location.

### Relationships and lifecycle

A run is created only after explicit user action. Its configuration is kept
with its result in session state; the expensive result may be disk-cached using
the package-source fingerprint. Changing only the displayed line-speed
measurement location does not change the simulation run.

## FEM Field State and Result

Each spatial node carries seven interleaved fields:

| Field | Meaning | Unit |
|---|---|---|
| `u_s` | Tangential velocity | m/s |
| `u_n` | Normal velocity | m/s |
| `F_s` | Tangential internal force / tension | N |
| `F_n` | Normal internal force / shear | N |
| `phi` | Tangent angle | rad |
| `nu_z` | Curvature | 1/m |
| `Gamma_z` | Curvature gradient | 1/m² |

The flat solution vector is node-major: field `f` at node `i` is indexed as
`i * NFIELDS + f`. Implementations must use the state module's constants and
helpers rather than hard-coded field offsets.

A simulation result contains the time grid, field history, spatial grid, and
derived coordinates and diagnostics such as positions, speeds, tension,
chord length, and tip deflection. Multi-domain results retain the ordered
subdomain layout and junctions.

## Component

A physical rod, line, or leader described by JSON metadata and a CSV profile.

| Attribute | Meaning / constraint |
|---|---|
| `name` | Human-readable name |
| `kind` | Component category (for example rod, line, or leader) |
| `length_m` | Positive component length; profile spans from zero to this value |
| `n_nodes` | Default discretisation size |
| `profile_csv` | Relative path to profile table |
| `columns` | Mapping from semantic profile values to CSV column names |
| `mass_mode` | `absolute` or AFTM-scaled |
| `eta_s` | Material relaxation time |
| `interp` | Currently `linear` |

Profile control points contain arc length `s_m` (strictly increasing from
0 through `length_m`), mass density `m_kg_per_m`, stiffness `EI_Nm2`, and
diameter `d_m`. At least two control points are required; array columns must
have matching length. Optional metadata may provide profile defaults and AFTM
scaling information. Values use SI units unless names specify otherwise.

## Rig and Junction

A rig is an ordered list of component JSON files with one coupling between
each adjacent pair. A junction identifies the adjacent component names and
has kind `pinned` or `welded`.

- **Pinned**: hinge; bending moment is not transmitted.
- **Welded**: continuous tangent angle and bending moment are transmitted.

The current Cast #1 rig order is rod → fly line → leader. The rod/line junction
is pinned and line/leader junction welded. A fly terminal mass is not part of
the current rig.

## Rod Measurement Set

A directory rooted at a `rod.yaml` file with schema identifier
`flycastsim.rod.measurement/1`. The file describes:

- Rod identity, make/model, line weight, assembled length, section masses,
  section lengths, balance points, and ferrule overlap when known.
- Mount clamp position and angle.
- Image calibration, pixel orientation, clamp and trace-start points, and
  optional tracked markers.
- Static-bend image sequence, loading information, trace direction, and
  excluded frames.
- Optional CCS load, deflection fraction, and action angle.
- Optional tip-mass/frequency CSV and clamp/load-point settings.

Unknown observations may be `null`. Image paths and test-data paths are
relative to the measurement folder. Units are SI unless explicitly marked as
grams, degrees, or pixels.

### Validation and fit lifecycle

Archives are safely extracted before loading. The application permits
excluding frames and requires usable calibration/traces. Fitting combines
static-bend, frequency, CCS, and section-mass evidence when present. If
absolute-scale data is missing, the fit must not be represented as a
meaningful absolute profile. A completed fit is exported, cached for reuse by
input and preset, and copied into a session-specific folder for current-session
use.

## Fitted Rod

A fitted rod consists of:

- `rod.json`: component metadata and profile linkage.
- `rod.csv`: spatial mass, stiffness, and diameter profiles.
- `fit_summary.json`: fitted inputs, parameters, diagnostics, and provenance.

The packaged fitted rods are PA905, XP590, and TCR590. App-generated fitted
rods are downloadable and available during the current session; the app does
not install them into the package.

## Runtime Cache Entry

| Attribute | Meaning |
|---|---|
| Source fingerprint | Invalidates computed results after package Python code changes |
| Input content digest | Identifies uploaded archive or guided-form content |
| Fit preset | Distinguishes fit configuration |
| Stored artifact | Extracted upload, trace, fit result, or simulation result |

Shared cache files are stored under a temporary server directory. Matching
uploads/fits may be reused across sessions. No fixed retention period is
promised. Session copies of a fitted rod are tracked separately from shared
cache artifacts.
