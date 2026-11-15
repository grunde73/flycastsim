# cast-stroke Specification

## Purpose
Describes a casting stroke as data: the rod-butt angle and the hand position over time. Covers the stroke file format, loading and saving strokes, the bundled Cast #1 stroke, and driving the Cast #1 simulation with a stroke.

## Requirements

### Requirement: Stroke file format
A stroke SHALL be stored as a JSON metadata file plus a CSV table. The JSON SHALL have `"kind": "stroke"`, a `name`, a `table_csv` path relative to the JSON file, and a `columns` mapping that names the CSV columns for time `t` [s] and rod-butt angle `angle` [deg]. The mapping MAY also name hand position columns `x` and `y` [m], which SHALL be given together or not at all. Other JSON keys, such as `description` and `source`, SHALL be kept as metadata.

#### Scenario: Stroke with angle and hand path
- **WHEN** a stroke file with time, angle and both hand columns is loaded
- **THEN** the loaded stroke holds the table values and the metadata from the JSON (`tests/unit/test_fem_stroke.py::test_load_stroke_reads_table_and_metadata`)

#### Scenario: Stroke without a hand path
- **WHEN** a stroke file with only time and angle columns is loaded
- **THEN** the hand position is zero and the hand velocity is zero at all times (`test_fem_stroke.py::test_stroke_without_hand_path_is_fixed`)

### Requirement: Stroke conventions
Time SHALL be in seconds relative to RSP (Rod Straight Position), so RSP is `t = 0`. The angle SHALL be the absolute tangent angle of the rod at the handle, with the casting direction as `+x`: 0 degrees is level forward and 90 degrees is straight up. The hand position SHALL be in metres in the same frame, with `+y` up.

#### Scenario: Bundled stroke follows the conventions
- **WHEN** the bundled Cast #1 stroke is loaded
- **THEN** its angle starts in the second quadrant, ends in the first quadrant, and its hand position moves in `+x` up to `t = 0` (`test_fem_cast.py::test_cast1_handle_angle_sweeps_q2_to_q1`, `test_fem_cast.py::test_cast1_hand_translates`)

### Requirement: Stroke evaluation between and outside samples
A stroke SHALL give the angle, hand position and hand velocity at any time. Between samples it SHALL pass through every sample without overshoot and with a continuous first derivative. Outside the sampled time range the angle and hand position SHALL hold their end values and the hand velocity SHALL be zero. The hand velocity SHALL be the time derivative of the interpolated hand position.

#### Scenario: Evaluation at the samples
- **WHEN** a stroke is evaluated at its sample times
- **THEN** it returns the sampled angle and hand position (`test_fem_stroke.py::test_stroke_passes_through_samples`)

#### Scenario: Evaluation outside the table
- **WHEN** a stroke is evaluated before its first or after its last sample
- **THEN** the angle and hand position equal the end values and the hand velocity is zero (`test_fem_stroke.py::test_stroke_holds_ends`)

#### Scenario: Velocity matches the position
- **WHEN** the hand velocity is compared with a finite difference of the hand position inside the table
- **THEN** they agree (`test_fem_stroke.py::test_hand_velocity_is_position_derivative`)

### Requirement: Invalid stroke files are rejected
Loading a stroke SHALL fail with a `ValueError` that names the problem when the JSON `kind` is not `stroke`, a required key or mapped column is missing, only one of the hand columns is given, the table has fewer than two rows, a value is not finite, or the times are not strictly increasing. A missing file SHALL fail with `FileNotFoundError`.

#### Scenario: Times not increasing
- **WHEN** a stroke table has a repeated or decreasing time
- **THEN** loading fails with a `ValueError` (`test_fem_stroke.py::test_load_stroke_rejects_invalid`)

#### Scenario: Wrong kind or missing column
- **WHEN** the JSON has another `kind`, lacks `columns`, or maps a column the CSV does not have
- **THEN** loading fails with a `ValueError` (`test_fem_stroke.py::test_load_stroke_rejects_invalid`)

#### Scenario: Unknown stroke source
- **WHEN** a stroke source is neither an existing path nor a bundled stroke name
- **THEN** loading fails with a `FileNotFoundError` (`test_fem_stroke.py::test_load_stroke_unknown_source`)

### Requirement: Coarse strokes give a warning
Loading a stroke SHALL give a `UserWarning` when the largest time step in its table is more than 10 ms, because the simulated cast is sensitive to how a coarse stroke is interpolated. The stroke SHALL still load.

#### Scenario: Coarse table
- **WHEN** a stroke sampled every 20 ms is loaded
- **THEN** a `UserWarning` about coarse sampling is given and the stroke is returned (`test_fem_stroke.py::test_coarse_stroke_warns`)

#### Scenario: Dense table
- **WHEN** the bundled Cast #1 stroke is loaded
- **THEN** no warning is given (`test_fem_stroke.py::test_bundled_cast1_stroke_loads_clean`)

### Requirement: Strokes can be saved
The library SHALL write a stroke to a folder as a JSON file plus a CSV table in the stroke file format. Loading the written files SHALL give back the same times, angles, hand positions, name and metadata.

#### Scenario: Round trip
- **WHEN** a stroke is saved and loaded again
- **THEN** the loaded stroke equals the original in its table values, name and metadata (`test_fem_stroke.py::test_save_stroke_round_trip`)

### Requirement: Cast #1 stroke is bundled
The package SHALL ship the Cast #1 stroke as stroke files, loadable by the name `cast1`. Its table SHALL cover -0.40 s to 0.13 s with a time step of 2.5 ms and include the hand path. Its metadata SHALL state the source of the stroke and that it was fitted by eye.

#### Scenario: Loading by name
- **WHEN** a stroke is loaded with the source `cast1`
- **THEN** the bundled Cast #1 stroke is returned, with the stated time range and step (`test_fem_stroke.py::test_bundled_cast1_stroke_loads_clean`)

#### Scenario: Stroke files are in the wheel
- **WHEN** the package is built
- **THEN** the stroke files are included, as required by the architecture requirement "Bundled data ships with the wheel" (`test_fem_stroke.py::test_bundled_cast1_stroke_loads_clean` loads them through package resources)

### Requirement: Cast #1 simulation takes a stroke
The Cast #1 simulation SHALL accept a stroke as a bundled name, a path to stroke files or a loaded stroke, and SHALL drive the handle angle and handle translation from it. Without a stroke argument it SHALL use the bundled Cast #1 stroke. The initial rod angle SHALL be the stroke's angle at the start of the simulated time span.

#### Scenario: Default stroke
- **WHEN** the Cast #1 simulation runs with no stroke argument and with the stroke `cast1`
- **THEN** the two results are identical (`test_fem_cast.py::test_simulate_cast1_default_stroke_is_bundled`)

#### Scenario: Custom stroke changes the cast
- **WHEN** the Cast #1 simulation runs with a stroke whose hand stays fixed
- **THEN** the handle node stays at the origin and the result differs from the default run (`test_fem_cast.py::test_simulate_cast1_with_custom_stroke`)

#### Scenario: Stroke from a path
- **WHEN** the Cast #1 simulation is given the path of a saved copy of the bundled stroke
- **THEN** the result is identical to the default run (`test_fem_cast.py::test_simulate_cast1_stroke_from_path`)

### Requirement: Cast #1 results stay within a stated tolerance
With the bundled stroke and default settings, the Cast #1 simulation SHALL stay close to the results from before the stroke became data, recorded in a reference file. The rod chord length SHALL agree within 0.05 mm, the tip deflection within 0.5 mm, node positions up to RSP within 0.1 mm, and node positions over the whole cast within 5 mm.

#### Scenario: Comparison with the recorded results
- **WHEN** the default Cast #1 simulation is compared with the recorded reference
- **THEN** every stated tolerance holds (`test_fem_cast.py::test_simulate_cast1_matches_reference`)
