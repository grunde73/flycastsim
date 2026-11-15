# aftm-line-standard Specification

## Purpose
Provides the AFTM (AFFTA) fly-line weight standard as public library data: the nominal head mass for each line weight, and the line mass per length derived from it, used to scale fly-line components to a chosen line weight.

## Requirements

### Requirement: AFTM weight table
The library SHALL provide the nominal AFTM head mass in grains for line weights 1 to 12, as a public table: 60, 80, 100, 120, 140, 160, 185, 210, 240, 280, 330 and 380 grains. The head SHALL be the first 30 ft (9.144 m) of line, and one grain SHALL be 64.79891 mg.

#### Scenario: Table values
- **WHEN** the public AFTM table is read
- **THEN** it holds the twelve stated weights and grain values, a head length of 9.144 m and a grain of 64.79891 mg (`tests/unit/test_fem_aftm.py::test_aftm_table_values`)

### Requirement: Head mass for a line weight
The library SHALL give the head mass in grams for a line weight. For a whole weight it SHALL be the table value converted to grams. For a weight between two whole weights it SHALL be linearly interpolated between them.

#### Scenario: Whole weights
- **WHEN** the head mass of a 5-wt and an 8-wt line is requested
- **THEN** it is about 9.07 g and 13.61 g (`test_fem_aftm.py::test_head_mass_whole_weights`)

#### Scenario: Between whole weights
- **WHEN** the head mass of a 4.5-wt line is requested
- **THEN** it is the mean of the 4-wt and 5-wt head masses (`test_fem_aftm.py::test_head_mass_interpolates`)

### Requirement: Line mass per length for a line weight
The library SHALL give the line mass per length in kg/m for a line weight, as the head mass spread evenly over the 9.144 m head. It SHALL increase with the line weight.

#### Scenario: A 5-wt line
- **WHEN** the mass per length of a 5-wt line is requested
- **THEN** it is about 0.99 g/m, and the values for weights 3 to 8 increase strictly (`test_fem_aftm.py::test_line_mass_per_length`)

### Requirement: Weights outside the table are rejected
A line weight below 1, above 12 or not finite SHALL give a `ValueError` that names the valid range, for both the head mass and the mass per length, and when a component is scaled to such a weight.

#### Scenario: Out-of-range weight
- **WHEN** the head mass or mass per length is requested for a weight of 0, 13 or NaN
- **THEN** a `ValueError` is raised (`test_fem_aftm.py::test_out_of_range_weight_rejected`)

#### Scenario: Component scaled to an out-of-range weight
- **WHEN** the bundled fly line component is loaded with an AFTM weight of 13
- **THEN** a `ValueError` is raised (`test_fem_aftm.py::test_component_rejects_out_of_range_weight`)

### Requirement: Results inside the table are unchanged
Moving the table to the public API SHALL NOT change any result for weights from 1 to 12: component mass profiles and the Cast #1 simulation SHALL be the same as before.

#### Scenario: Cast #1 result
- **WHEN** the default Cast #1 simulation is run
- **THEN** it stays within the tolerances of the recorded reference (`tests/unit/test_fem_cast.py::test_simulate_cast1_matches_reference`), and the head masses for weights 1 to 12 equal the values computed before the change (`test_fem_aftm.py::test_head_mass_whole_weights` checks them to 1e-12 g)
