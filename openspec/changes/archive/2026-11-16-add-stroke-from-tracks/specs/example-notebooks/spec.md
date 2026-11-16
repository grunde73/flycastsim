# Spec Delta

## MODIFIED Requirements

### Requirement: Notebooks state the limits of each step
A step notebook SHALL say where the library does not yet support its workflow step in full, so that a reader does not look for a feature that is missing.

#### Scenario: Casting parameters notebook
- **WHEN** `04_casting_parameters.ipynb` is read
- **THEN** it loads a stroke from stroke files, makes a stroke from tracked points, and states that the points must be tracked in another program because the library does not yet read video or track points itself, that a stroke cannot yet be made from sensor data, and that a coarsely sampled stroke gives unreliable results (`test_notebook_executes`; the statements rely on review)

#### Scenario: Rod characteristics notebook
- **WHEN** `02_rod_characteristics.ipynb` is read
- **THEN** it states that the fit cell is switched off by default and how long a fit takes (relies on review)
