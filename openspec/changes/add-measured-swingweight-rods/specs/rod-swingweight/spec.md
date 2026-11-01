# Spec Delta

## ADDED Requirements

### Requirement: Swingweight measurement file format
The package SHALL read swingweight measurement CSV files with `#` comment lines, the header `length[m],mass_center[m],mass[g]`, one overall rod row, and then section rows ordered tip to butt. Malformed files SHALL raise `ValueError`.

#### Scenario: Valid file
- **WHEN** a valid measurement file is loaded
- **THEN** sections are returned ordered butt to tip, in SI units, with the overall row as assembled length, measured balance point and measured mass (`test_measurement_file_rows_and_units`)

#### Scenario: Unexpected header
- **WHEN** the header differs from the expected columns
- **THEN** `ValueError` is raised (`test_measurement_file_bad_header_raises`)

#### Scenario: No section rows
- **WHEN** a file has an overall row but no section rows
- **THEN** `ValueError` is raised (`test_measurement_file_without_sections_raises`)

### Requirement: Bundled measured rods
The package SHALL provide the PA905 and TCR590 measurements as bundled data with make, model and reel-seat status, available from an installed wheel. They SHALL NOT change the worked-example rods from the paper.

#### Scenario: Loading the measured rods
- **WHEN** the bundled measured rods are loaded
- **THEN** PA905 has three sections and TCR590 has four, each estimable by the swingweight estimator (`test_measured_rods_load_and_estimate`)

#### Scenario: Estimated values are stable
- **WHEN** the measured rods are estimated as finished rods
- **THEN** PA905 gives 74.8 g·m² and TCR590 gives 72.5 g·m², each within 0.1 g·m² (`test_measured_rods_estimates`)

#### Scenario: Worked examples are unaffected
- **WHEN** the worked-example rods are loaded
- **THEN** they contain only the rods from the paper (`test_example_rods_match_paper_totals`)

#### Scenario: Shipped in the wheel
- **WHEN** the wheel is built
- **THEN** the measured rod files are included (`test_wheel_ships_bundled_data`)

### Requirement: Measurement consistency check
The package SHALL report the summed section mass and the balance point calculated from the sections, using ferrule-corrected positions and the measured butt balance point, next to the measured overall values. It SHALL report differences and SHALL NOT reject a rod because of them.

#### Scenario: Consistent rod
- **WHEN** PA905 is checked
- **THEN** the mass difference is below 0.05 g and the balance point difference is below 0.005 m (`test_consistency_check_values`)

#### Scenario: Rod with a discrepancy
- **WHEN** TCR590 is checked
- **THEN** a mass difference of about 1.1 g and a balance point difference of about 0.014 m are reported without an error (`test_consistency_check_values`)

### Requirement: Measured rods as app presets
The app's Swingweight view SHALL offer the bundled measured rods as presets alongside the worked examples, filling in their sections, assembled length and reel-seat status.

#### Scenario: Selecting a measured rod
- **WHEN** a measured rod is selected as the preset
- **THEN** the view shows its estimated swingweight without an error (`test_app_measured_rod_presets`)

#### Scenario: Preset wording
- **WHEN** the preset list is shown
- **THEN** its help text no longer describes every preset as coming from the paper (relies on review)
