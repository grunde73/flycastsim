# Spec Delta

## MODIFIED Requirements

### Requirement: Notebooks state the limits of each step
A step notebook SHALL say where the library does not yet support its workflow step in full, so that a reader does not look for a feature that is missing.

#### Scenario: Casting parameters notebook
- **WHEN** `04_casting_parameters.ipynb` is read
- **THEN** it loads a stroke from stroke files, and states that a stroke cannot yet be extracted from video or sensor data and that a coarsely sampled stroke gives unreliable results (`test_notebook_executes`; the statements rely on review)

#### Scenario: Rod characteristics notebook
- **WHEN** `02_rod_characteristics.ipynb` is read
- **THEN** it states that the fit cell is switched off by default and how long a fit takes (relies on review)
