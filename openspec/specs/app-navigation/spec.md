# app-navigation Specification

## Purpose
Defines which sections the Streamlit app offers, the order they appear in, and how the app presents the five-step casting workflow, including the switch that controls whether the cast simulation section is shown.

## Requirements

### Requirement: Default sections
With the cast switch off, the app SHALL offer exactly these sections, in this order: "Introduction", "Simple 1D model" and "Rod parameters". The "Sample fly cast" section SHALL NOT be offered and its page SHALL NOT run.

#### Scenario: App started without the switch
- **WHEN** the app starts with `FLYCASTSIM_SHOW_CAST` unset
- **THEN** the section selector lists "Introduction", "Simple 1D model" and "Rod parameters", and nothing else (`test_default_sections_hide_cast`)

### Requirement: Cast section switch
The environment variable `FLYCASTSIM_SHOW_CAST` SHALL control the "Sample fly cast" section. The values `1`, `true`, `yes` and `on`, in any letter case, SHALL turn it on. Any other value, an empty value or an unset variable SHALL leave it off. When on, the section SHALL be listed last, after "Rod parameters", and SHALL behave as it did before this change.

#### Scenario: Switch turned on
- **WHEN** the app starts with `FLYCASTSIM_SHOW_CAST=1`
- **THEN** "Sample fly cast" is the last section in the selector, and selecting it shows the Cast #1 page without an error (`test_cast_switch_shows_cast_section`)

#### Scenario: Recognised and unrecognised values
- **WHEN** the variable is set to `true`, `YES` or `on`, and then to `0`, `false`, an empty string or `maybe`
- **THEN** the section is offered for the first three and not for the others (`test_cast_switch_values`)

### Requirement: Workflow on the Introduction page
The Introduction page SHALL present the five-step workflow: the standalone simple 1-D model, rod characteristics, line and leader characteristics, casting parameters, and simulating a fly cast from the previous three. It SHALL state which steps the running app offers, and SHALL describe the steps it does not offer as not yet available.

#### Scenario: Introduction with the switch off
- **WHEN** the Introduction page is shown with the switch off
- **THEN** it lists all five steps, and marks line and leader, casting parameters and the cast simulation as not yet available (`test_intro_presents_workflow`)

#### Scenario: Introduction with the switch on
- **WHEN** the Introduction page is shown with the switch on
- **THEN** it marks the cast simulation as available in "Sample fly cast" (`test_intro_presents_workflow`)

### Requirement: No pointers to a hidden section
With the cast switch off, the app SHALL NOT tell the user that something can be done in the "Sample fly cast" section or in the Cast #1 rod selector.

#### Scenario: Visible pages with the switch off
- **WHEN** the Introduction page and the Stiffness profiles view are shown with the switch off
- **THEN** neither contains the text "Sample fly cast" (`test_hidden_cast_is_not_mentioned`)

#### Scenario: Fit result message with the switch off
- **WHEN** a rod fit completes in the Upload & fit view with the switch off
- **THEN** the result message names the Stiffness profiles view only (relies on review, since a fit is too slow for the unit tests)
