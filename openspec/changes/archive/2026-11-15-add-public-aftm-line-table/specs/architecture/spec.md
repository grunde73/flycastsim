# Spec Delta

## MODIFIED Requirements

### Requirement: App uses the public API
`streamlit_app.py` and `rod_profile_pages.py` SHALL NOT import private `flycastsim` names, meaning any module or name with a leading underscore. There are no exceptions. Checked by: `tests/unit/test_architecture.py::test_app_imports_only_public_api`.

#### Scenario: The app imports a private name
- **WHEN** an app file imports any private `flycastsim` name
- **THEN** the test fails
