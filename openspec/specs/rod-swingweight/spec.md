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
