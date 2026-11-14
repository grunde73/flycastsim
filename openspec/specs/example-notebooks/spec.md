# example-notebooks Specification

## Purpose
Defines the example notebooks that show how to use the `flycastsim` library along the five-step casting workflow, and the guarantees that keep them runnable. Scenario tests are in `tests/unit/test_example_notebooks.py`.

## Requirements

### Requirement: One notebook per workflow step
The repo SHALL provide one example notebook for each workflow step in `examples/notebooks/`, named with the step number: `01_simple_1d_model`, `02_rod_characteristics`, `03_line_and_leader`, `04_casting_parameters` and `05_simulate_cast`. Each SHALL be runnable on its own, without running another notebook first.

#### Scenario: The step notebooks exist
- **WHEN** the `examples/notebooks/` folder is listed
- **THEN** it contains the five step notebooks, each with a title naming its workflow step (`test_step_notebooks_exist`)

#### Scenario: A step notebook is run alone
- **WHEN** any one step notebook is executed in a fresh kernel
- **THEN** it finishes without an error (`test_notebook_executes`)

### Requirement: Complete workflow notebook
The repo SHALL provide `examples/notebooks/complete_workflow.ipynb`, which runs steps 2 to 5 in sequence: it selects a rod, selects a line and leader, shows the casting stroke, and simulates a cast with those inputs.

#### Scenario: The complete workflow is run
- **WHEN** `complete_workflow.ipynb` is executed in a fresh kernel
- **THEN** it finishes without an error and has a section for each of steps 2 to 5 (`test_notebook_executes`, `test_complete_workflow_covers_steps`)

### Requirement: Notebooks run from a clean checkout
Every example notebook SHALL execute from top to bottom after `uv sync`, using only bundled package data and files in the repo, without network access and without user input. The test suite SHALL execute every example notebook.

#### Scenario: Notebooks are executed by the test suite
- **WHEN** the test suite runs
- **THEN** every notebook in `examples/notebooks/` is executed and none raises an error (`test_notebook_executes`)

#### Scenario: A notebook is added without being runnable
- **WHEN** a notebook that raises an error is added to `examples/notebooks/`
- **THEN** the test suite fails, because the test collects the notebooks from the folder (`test_notebook_executes`)

### Requirement: Notebooks use the public API
Example notebooks SHALL import only public `flycastsim` names, meaning no module or name with a leading underscore.

#### Scenario: A notebook imports a private name
- **WHEN** a code cell imports a `flycastsim` name with a leading underscore
- **THEN** the test suite fails (`test_notebook_imports_only_public_api`)

### Requirement: Notebooks are committed without outputs
Example notebooks SHALL be committed with no cell outputs and no execution counts, so that changes to them stay reviewable.

#### Scenario: A notebook is committed with outputs
- **WHEN** a notebook in `examples/notebooks/` contains a cell output or an execution count
- **THEN** the test suite fails (`test_notebook_has_no_outputs`)

### Requirement: Notebook tools stay out of the app deployment
The packages needed only to run or test the notebooks SHALL NOT be installed in the Streamlit deployment: they SHALL NOT appear in `requirements.txt` or in the `app` dependency group, and the app SHALL NOT import them.

#### Scenario: Requirements file after adding the notebook tools
- **WHEN** the notebook tools are added to the project
- **THEN** `requirements.txt` contains neither `ipykernel` nor `nbclient` and still matches the export of the `app` group (`test_notebook_tools_not_in_app_requirements`, `scripts/check_requirements.sh`)

### Requirement: Notebooks state the limits of each step
A step notebook SHALL say where the library does not yet support its workflow step in full, so that a reader does not look for a feature that is missing.

#### Scenario: Casting parameters notebook
- **WHEN** `04_casting_parameters.ipynb` is read
- **THEN** it states that a stroke cannot yet be loaded from a file or passed to the Cast #1 simulation (relies on review)

#### Scenario: Rod characteristics notebook
- **WHEN** `02_rod_characteristics.ipynb` is read
- **THEN** it states that the fit cell is switched off by default and how long a fit takes (relies on review)
