# Component and Rig Data Contract

## Component metadata

Each tackle component is described by JSON metadata and a relative CSV profile
path. The current metadata shape includes:

| Key | Required / optional | Contract |
|---|---|---|
| `name` | Required | Human-readable component label |
| `kind` | Required | Physical kind such as `rod`, `line`, or `leader` |
| `length_m` | Required | Total length in metres |
| `n_nodes` | Required | Default grid size, at least 3 for FEM discretisation |
| `profile_csv` | Required | CSV path relative to metadata file |
| `columns` | Required | Semantic-to-CSV column-name mapping |
| `mass_mode` | Optional | `absolute` or `scaled_by_aftm` |
| `aftm_weight` | Conditional | Required if AFTM scaling has no run-time override |
| `aftm_head_length_m` | Conditional | Head length used to scale line mass |
| `eta_s` | Optional | Material relaxation time in seconds |
| `interp` | Optional | Currently `linear` |

The current profile CSV uses `s_m`, `m_kg_per_m`, `EI_Nm2`, and `d_m`.
Arc-length positions must begin at zero, increase strictly, and end at
`length_m`. Each physical profile column must match the number of control
points. Linear interpolation samples the profile onto the component grid.

Masses in `absolute` mode use kg/m directly. AFTM-scaled mass uses the line
standard to scale the profile shape so the mass of the configured head length
matches the selected AFTM head mass.

## Rig metadata

A rig JSON file lists:

- `components`: ordered relative component metadata paths.
- `junctions`: adjacent component-name pairs and a `kind`.

Junction kinds are `pinned` and `welded`. The Cast #1 rig is rod → line →
leader, with pinned rod/line and welded line/leader connections. A fly
terminal point mass is not currently defined.

## Packaging

The shipped component and fitted-rod JSON/CSV files live under
`src/flycastsim/data/` and are included in distributions via `MANIFEST.in`.
Load bundled data using package loaders/resources rather than assuming a
working-directory-relative path. Large measured source assets under `assets/`
are repository-only and are not installed package data.

## Validation

Reject malformed metadata, missing referenced files/columns, unsupported
interpolation modes, invalid profile lengths, non-increasing arc coordinates,
and profiles whose end coordinate disagrees with the declared length. Errors
must identify the invalid file or field.
