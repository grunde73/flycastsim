# rod-swingweight Specification

## Purpose
Estimate a fly rod's swingweight, its moment of inertia about the butt axis, from per-section measurements, following Løvoll & Angus, "Measuring fly rod swingweight" (2008). Scenario tests are in `tests/unit/test_rod_swingweight.py`.

## Requirements

### Requirement: Swingweight estimate matches the published method
`flycastsim.swingweight` SHALL compute the total moment of inertia about the rod butt as the sum of the per-section values from the paper's equations, for sections ordered butt to tip.

#### Scenario: Bundled example rods
- **WHEN** the rods from `load_example_rods` are estimated
- **THEN** each total is within 1 g·m² of the value in the paper (`test_example_rods_match_paper_totals`)

#### Scenario: Per-section breakdown
- **WHEN** the Dan Craft FT 905-4 blank is estimated without a reel seat
- **THEN** the section values match the paper within 0.05 g·m² (`test_dan_craft_blank_per_section`)

### Requirement: Section moment of inertia
Each section's moment of inertia SHALL assume mass density falling linearly from the thick end, and SHALL be shifted to the butt axis with the parallel-axis theorem.

#### Scenario: About the section mass centre
- **WHEN** `section_moi_about_cm` is evaluated
- **THEN** it equals the paper's closed form (`test_section_moi_about_cm_formula`)

#### Scenario: About the butt axis
- **WHEN** `section_moi` is evaluated at distance `d`
- **THEN** it equals `I_cm + m d²` (`test_section_moi_parallel_axis`)

### Requirement: Ferrule overlap is removed
The overlap per ferrule SHALL be the sum of section lengths minus the assembled length, divided by the number of ferrules, and SHALL be removed from each section's distance to the butt.

#### Scenario: Multi-piece rod
- **WHEN** a rod with several sections is estimated
- **THEN** the result reports the ferrule count and the overlap from that formula (`test_ferrule_overlap_estimate`)

#### Scenario: Single-section blank
- **WHEN** one section is estimated without a reel seat
- **THEN** there are no ferrules, no overlap, and the measured balance point is used (`test_single_section_blank`)

### Requirement: Reel seat and grip correction
For a finished rod, the butt section SHALL be corrected by inferring the blank's mass centre from the section above and modelling the reel seat and grip as a uniform cylinder, 0.16 m long by default. A bare blank SHALL skip the correction.

#### Scenario: Mass split
- **WHEN** the correction is applied to a butt section
- **THEN** blank and reel-seat masses add up to the measured butt mass, and the cylinder term follows eq. 9 (`test_reel_seat_grip_mass_split`)

#### Scenario: Only the butt section changes
- **WHEN** the same rod is estimated with and without the correction
- **THEN** only the butt section's value differs (`test_reel_seat_increases_butt_moi`)

### Requirement: Invalid input is rejected
The estimator SHALL raise `ValueError` for input it cannot estimate.

#### Scenario: No sections
- **WHEN** an empty section list is passed
- **THEN** `ValueError` is raised (`test_empty_sections_raises`)

#### Scenario: Reel seat on a single section
- **WHEN** the reel-seat correction is requested for a single section
- **THEN** `ValueError` is raised (`test_single_section_reel_seat_raises`)

### Requirement: Results are available in both units
Results SHALL be in kg·m², with `swingweight_gm2` giving the paper's g·m².

#### Scenario: Unit conversion
- **WHEN** a result is read in both units
- **THEN** `swingweight_gm2` is 1000 times `swingweight` (`test_swingweight_units_consistency`)

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
