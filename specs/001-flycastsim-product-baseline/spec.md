# Feature Specification: flycastsim Product Baseline

**Feature Branch**: `spec_driven_dev`

**Created**: 2026-10-19

**Status**: Draft

**Input**: User description: "Create a complete, structured description of the
current software and its future plans so a coding agent can rebuild it from
scratch."

## Purpose and Scope

This is an as-built product baseline for the version of flycastsim present in
the repository when this specification was drafted. It describes observable
user workflows, model capabilities, data, constraints, and known limitations
that a coding agent would need to reproduce the current software.

This is an inventory, not a proposal to rewrite the software. Requirements in
this document describe current behavior unless explicitly labeled as future
work. The future-work section is a non-binding backlog; none of those items is
part of the current product contract. A selected future item must be promoted
to its own feature specification before implementation.

## Clarifications

### Session 2026-10-19

- Q: Should the baseline specification contain all equations, schemas, and
  numerical details needed to rebuild flycastsim, or may it rely on the
  repository’s linked technical documents and data as required references? →
  A: Keep the baseline focused on product behavior, and treat linked technical
  documents, tests, and data as required companion references.
- Q: Should rebuilding the current software include publishing its Streamlit
  app for public access, or is a locally runnable app sufficient? →
  A: Keep public deployment as today, handled by a GitHub task on a pull
  request or merge into `main`.
- Q: When the GitHub task runs for a pull request, should it publish a preview,
  or update the same public app that is deployed after a merge into `main`? →
  A: Pull requests run validation or a preview; merging into `main` publishes
  the public app.
- Q: Should a rebuild preserve the current shared temporary cache for uploaded
  rod datasets, or isolate and remove each upload after its session? →
  A: Preserve shared temporary caching by content and reuse matching uploads
  and fits; there is no fixed retention guarantee.

## As-Built Product Description

### Product and users

flycastsim is a Python library and browser-based Streamlit application for
exploring and simulating fly casts. It provides:

- A deliberately simplified one-dimensional brick-spring-car model for
  exploring relationships between drive motion, effective rod stiffness,
  line mass, speed, and work path.
- A planar continuum finite-element-style model of the coupled rod, fly line,
  and leader, including a sample cast based on recorded footage.
- Rod tools for estimating swingweight and fitting bending-stiffness and mass
  profiles from measurements.

The product is an alpha-stage research and demonstration tool. Cast #1 is a
qualitative comparison to a recorded cast, not a quantitatively validated
prediction of all casting behavior.

No numerical uptime, concurrency, or response-time targets are defined. The
publicly hosted app is resource-limited: long rod fits can be slow, and
animations may be affected by available bandwidth.

### User-facing application

The Streamlit application has three main areas: the simple model, Sample fly
cast / Cast #1, and Rod parameters. It is run from the repository with
`uv run streamlit run streamlit_app.py`.

The app is also publicly available at its hosted Streamlit URL. A GitHub task
runs validation or a preview for pull requests; merging into `main` publishes
the public app.

#### Simple 1-D model

The user can change spring stiffness, brick mass, car maximum speed,
acceleration-turn time, and full-stop time. The application computes a
reference case and the selected case, plots selectable result columns, can
mark key events, and can show a client-side animation. If the stop time is not
later than the turn time, it is moved to 0.01 seconds after the turn time and
the user is warned.

Current control ranges are:

- Spring stiffness: 0.5–3.0 N/m, in 0.1 N/m increments; reference 1.0 N/m.
- Brick mass: 5–40 g, in 1 g increments; reference 10 g.
- Car maximum speed: 3–40 m/s, in 1 m/s increments; reference 18 m/s.
- Turn time: 0.05–1.0 s, in 0.01 s increments; reference 0.30 s.
- Full-stop time: 0.05–1.0 s, in 0.01 s increments; reference 0.45 s.
- Simulation duration: 2 seconds.

The model is an explanatory forced oscillator, not a full rod-and-line
simulation.

#### Cast #1

Cast #1 reproduces the geometry and loading pattern of a recorded overhead
cast from *The Rod & The Cast*. The cast uses a driven rod-butt angle sweep
fitted by eye, with a forward hand translation, a full line and leader of
approximately 12.7 m, and an initial line layout behind the caster at about
5 degrees below horizontal. Time is referenced to Rod Straight Position
(RSP, t = 0); measured event frames include MAV, MCL, RSP, and MCF.

The user can select:

- AFTM line weight 3–8.
- The original tabulated T&T Paradigm rod, one of three packaged measured
  rods (PA905, XP590, TCR590), or a rod fitted during the current app session.
- Rod stiffness scale from 0.5 to 2.0, default 1.0.
- Grid size of 101, 121, or 141 nodes, default 101.
- Air drag and material damping, both off by default.
- Stroboscopic snapshots (on by default) and an imaginary rigid-rod overlay
  (off by default).
- A line-speed measurement location measured back from the line tip. Changing
  that location only changes the displayed measurement and does not rerun the
  simulation.

For fitted rods, rod diameter is not measured. The user can use the stretched
Cast #1 taper or specify a linear butt-to-tip taper. The simulation starts only
when the user selects **Run simulation**; parameter changes alone do not launch
a run. Results and their parameters are retained for re-rendering and cached
on disk using a fingerprint of package source code.

The result view compares simulated rod chord length with the measured curve,
and can display cast animation, snapshots, line speed, tip deflection, and
other cast diagnostics. The comparison is qualitative: the input stroke was
tuned to the stiffer tabulated rod, and the current tackle model does not have
a terminal fly mass or drag condition capable of reproducing a crisp loop.

#### Rod parameters: swingweight

The user can select a worked-example rod or enter measurements for a custom
rod. For each section, the measurements are mass, length, and balance point
from the thick end. The user also supplies assembled rod length and whether
the rod has a reel seat and grip.

The result is the rod's moment of inertia about the butt, its per-section
contributions, ferrule-overlap estimate, and (for finished rods) the
reel-seat/grip correction. The app displays the measurements and a
contribution chart. The estimator assumes linear mass density within each
section and uses the Løvoll and Angus (2008) method.

#### Rod parameters: stiffness profiles

The user can compare any combination of the bundled fitted rods and rods fitted
during the current session. The view presents bending stiffness EI(s), mass
density μ(s), a summary table, frequency and fitted-load comparisons, and
traced bend-test centre lines against modelled shapes.

The bundled profiles are T&T Paradigm 905-3 (PA905), Sage XP 590-4 (XP590),
and Sage TCR 590-4 (TCR590). PA905's mass profile remains a generic estimate
because measured section masses are not available.

#### Rod parameters: upload and fit

The user can fit a rod from either a zip archive of a rod data folder or a
guided form. A measurement set can contain rod metadata, static-bend images,
tip-mass frequency measurements, optional Common Cents System (CCS) data,
optional section masses, and image calibration information. Zip paths are
relative to the archive's rod folder. The guided form accepts the equivalent
rod details and uploads, allows images to be excluded, and lets the user place
the clamp and trace-start points on an image, with a tracing preview.

The fit estimates stiffness and mass profiles and related image-transform,
load, and mount parameters. The workflow supports quick and full fit presets,
reports progress, and displays fitted results and fit diagnostics. The result
can be downloaded as a zip. A rod fitted in the app is available to the
comparison view and Cast #1 for the remainder of that session; it is not
installed into the Python package by the app.

Uploaded archives and reusable fits are cached in shared temporary server
storage, keyed by the input content and fit preset, so matching work can be
reused across sessions. A session-specific copy of a fitted rod is used by the
current session. The application does not promise a fixed retention period for
the shared temporary cache.

Inputs lacking an absolute stiffness/mass scale are insufficient on their own:
the CCS load, known tip masses and frequency measurements, and measured
section masses provide scale information. EI behind the clamp is held
constant because it is not observed, and EI close to the tip is poorly
constrained because bending moment vanishes there. Frames that disagree with
the fit (including the unloaded frame for the bundled rods) may be excluded.

### Python library

The installable `flycastsim` package exposes the simple model, FEM and rod
modules. It can be used directly from Python independently of the Streamlit
interface. Major public capabilities include:

- The brick-spring model, with plotting and animation helpers.
- FEM domain and component construction, static and dynamic solvers,
  multi-domain coupling, cast simulations, drag, coordinate reconstruction,
  and cast-result plotting helpers.
- Rod swingweight, elastica and vibration solvers, image tracing, measurement
  loading, profile fitting, fitted-rod loading, and safe archive handling.

Documented entry points include `brick_spring_simple`,
`flycastsim.fem.simulate_cast`, `flycastsim.fem.simulate_cast1`,
`flycastsim.rod.compute_swingweight` (also exported as `swingweight`),
`flycastsim.rod.fit_rod`, `flycastsim.rod.load_fitted_rods`, and the FEM
component/rig loaders. The simple model returns tabular time-series results;
the FEM simulations return time-dependent fields and derived cast data.

The numerical FEM core is plotting-free; plotting and animation adapters are
outside that core.

### Model behavior and numerical contract

The FEM model is planar and uses seven coupled fields per node:
tangential and normal velocities, tangential and normal internal forces,
tangent angle, curvature, and curvature gradient. It includes kinematic and
momentum balances, gravity, bending, and tension. Optional terms are
Reynolds-number air drag and Kelvin-Voigt material damping. Multiple beam-line
subdomains can be connected at pinned or welded junctions; the current
sample rig contains rod, line, and leader.

The current spatial discretisation is staggered and second order. Time
integration uses a first-order generalised-alpha method, Newton-Raphson
iterations, and a sparse two-colour finite-difference Jacobian solved with
SciPy sparse LU. The solver reuses its factorised Jacobian and caches constant
material terms without changing the converged solution.

The FEM engine is verified against six exact cases: static hanging chain,
static towed line, static non-uniform beam, dynamic oscillating beam, dynamic
hanging chain, and dynamic travelling wave. Tests also check second-order
spatial convergence. These verification cases are acceptance criteria for
reproducing or changing the numerical core.

### Data and packaging

The package requires Python >=3.12 and is managed with `uv`. The Streamlit app
and development tools are default dependency groups; documentation tools are
an optional extra. `requirements.txt` is generated from the dependency
configuration and must not be edited as an independent source of truth.

Packaged component and fitted-rod data live under
`src/flycastsim/data/`. Component metadata is JSON and spatial profiles are
CSV; rig metadata connects the rod, line, and leader. Three fitted rods and
worked-example swingweight measurements are included. Large measurement
datasets and reference assets live under repository `assets/` and are not
included as installed package data.

### Current architecture

- `src/flycastsim/sho/` contains the 1-D oscillator model and its plotting and
  animation helpers.
- `src/flycastsim/fem/` contains the continuum engine. Its data flow is
  component/domain construction, staggered spatial operators and boundary
  conditions, seven-field state packing, generalised-alpha integration and
  nonlinear solving, then cast and multi-domain orchestration.
- `src/flycastsim/rod/` contains swingweight, static elastica, vibration,
  imaging, profile fitting, measurement and fitted-rod loaders, and archive
  utilities.
- `streamlit_app.py` owns the main application and its model/cast views.
- `rod_profile_pages.py` and `fem_helpers.py` provide presentation and plotting
  helpers. Expensive fits, traces, and Cast #1 simulations use cached results;
  package-source fingerprints invalidate results when package code changes.
- `tests/unit/` contains focused tests for the oscillator, FEM, rod tools, and
  archive handling.

### Evidence and detailed references

This baseline is based on the current source tree, README, tests, and existing
documentation. For a reconstruction, this specification defines product
behavior and scope; the documents below, together with their referenced data
and tests, are required companion references for equations, assumptions, input
schemas, and detailed examples:

- `README.md`
- `docs/index.rst`
- `docs/brick_spring.rst`
- `docs/fem.rst`
- `docs/rod.rst`
- `docs/rod_profile.rst`
- `docs/planned.rst`
- `.github/copilot-instructions.md`

## User Scenarios & Testing

### User Story 1 - Explore the simple casting model (Priority: P1)

As a user learning how drive motion, effective stiffness, and line mass
interact, I can change the toy model's parameters and compare its response with
the reference case.

**Why this priority**: It is a complete, low-complexity way to explore the
basic model without requiring measured tackle or a FEM configuration.

**Independent Test**: Start the app, change the spring stiffness or brick mass,
and verify that the selected response and reference response are both plotted.

**Acceptance Scenarios**:

1. **Given** the default parameters, **When** the simple model view opens,
   **Then** it displays the reference response and selectable result plots.
2. **Given** a custom set of valid parameters, **When** the user changes a
   parameter, **Then** the plots reflect the custom response and can compare it
   with the reference.
3. **Given** a stop time that is not later than the turn time, **When** the
   simulation parameters are evaluated, **Then** the app warns the user and
   uses a stop time 0.01 seconds later than the turn time.
4. **Given** the animation option is enabled, **When** results are displayed,
   **Then** the user can inspect a client-side animation of the simple model.

### User Story 2 - Run the reference cast (Priority: P1)

As a user exploring a real recorded cast, I can select line weight and rod,
run Cast #1, and inspect the simulated cast alongside measured geometry and
event data.

**Why this priority**: This is the main demonstration of the coupled
rod-line-leader continuum engine.

**Independent Test**: Run Cast #1 with default settings and verify that the
result contains time-dependent FEM fields, reconstructed positions, chord
comparison, and the available cast visualisations.

**Acceptance Scenarios**:

1. **Given** no prior run, **When** the user changes a Cast #1 setting,
   **Then** the simulation does not run until **Run simulation** is selected.
2. **Given** a supported AFTM line weight and rod, **When** the user runs the
   simulation, **Then** the selected rig is simulated and results are shown
   against the measured Cast #1 curve and event frames.
3. **Given** a fitted rod is selected, **When** the user selects a supported
   diameter mode, **Then** that diameter is used for the simulation's drag
   geometry.
4. **Given** a completed run, **When** only the line-speed measurement point
   is changed, **Then** the displayed measurement updates without another
   simulation.

### User Story 3 - Estimate rod swingweight (Priority: P1)

As a rod owner or measurer, I can load an example or enter section
measurements and obtain the rod's butt-axis moment of inertia and section
contributions.

**Why this priority**: It provides an independent rod-characterisation tool
that does not require image data or an FEM simulation.

**Independent Test**: Enter the worked-example section measurements and verify
the resulting swingweight against the published value and unit tolerance.

**Acceptance Scenarios**:

1. **Given** a bundled worked example, **When** it is selected, **Then** its
   section measurements populate the editable table.
2. **Given** valid section masses, lengths, balance points, assembled length,
   and reel-seat choice, **When** the estimator runs, **Then** the app reports
   total swingweight, section contributions, ferrule overlap, and the
   applicable reel-seat/grip correction.
3. **Given** a bare blank, **When** the user disables the finished-rod
   correction, **Then** no reel-seat/grip correction is applied.

### User Story 4 - Fit and compare a measured rod (Priority: P1)

As a rod measurer, I can provide rod measurements and bend-test images, fit a
stiffness and mass profile, review the fit, download the result, and use it in
the current app session.

**Why this priority**: Measured rod properties replace guessed rod profiles
and make user-supplied rods available to Cast #1.

**Independent Test**: Use a bundled measurement dataset through the zip flow;
verify that tracing preview, fit outputs, downloadable rod data, and session
availability are produced.

**Acceptance Scenarios**:

1. **Given** a valid rod archive, **When** it is uploaded, **Then** its
   measurement description and relative-path data are safely extracted and
   made available for tracing and fitting.
2. **Given** guided-form measurements and image uploads, **When** the user
   places the clamp and trace-start points and requests a preview, **Then** the
   app displays the tracing overlay and identifies points not used by the fit.
3. **Given** a prepared dataset and selected fit preset, **When** the user
   starts a fit, **Then** progress and fit status are reported and the fitted
   data can be reviewed and downloaded.
4. **Given** a successful fit, **When** the same app session continues,
   **Then** the fitted rod is available in the comparison view and Cast #1
   rod selector.
5. **Given** the same uploaded measurement set and fit preset are submitted
   again, **When** a matching cached fit is available, **Then** the app can
   reuse it rather than repeat the fit.

### User Story 5 - Use the models programmatically (Priority: P2)

As a Python user, I can install the package and call its documented model and
rod APIs without importing or running the Streamlit application.

**Why this priority**: The library is a separately stated product surface and
supports scripting, testing, and future integrations.

**Independent Test**: Install the package in a clean Python >=3.12 environment
and run a documented example for the simple model, FEM cast, and rod tools.

**Acceptance Scenarios**:

1. **Given** the package is installed, **When** a user imports its public
   modules, **Then** model computations are available independently of
   Streamlit.
2. **Given** a packaged rig or fitted rod, **When** the package loaders are
   used, **Then** the data can be used to construct components and run a
   simulation.

### User Story 6 - Access the hosted application (Priority: P2)

As a flycastsim user, I can access the publicly hosted Streamlit app without
installing the package locally.

**Why this priority**: Public hosting is a documented way to use the app and
must remain available when reproducing the current product.

**Independent Test**: Open the public app URL in a browser and verify that the
application loads; verify that pull requests run validation or a preview and
that merging into `main` triggers publication of the public app.

**Acceptance Scenarios**:

1. **Given** a user with a browser, **When** they open the public app URL,
   **Then** the Streamlit application is available.
2. **Given** a pull request, **When** the GitHub task runs, **Then** it
   performs validation or creates a preview without replacing the public app.
3. **Given** a merge into `main`, **When** the GitHub task runs, **Then** it
   publishes the updated public app.

### Edge Cases

- Invalid time ordering in the 1-D model is corrected with a visible warning.
- Missing or inconsistent image calibration, traces, frame loads, or absolute
  stiffness scale can prevent a meaningful rod fit and must not be presented
  as a successful fit.
- The fitted EI profile is not measured behind the clamp and is poorly
  constrained near the tip; those regions must not be represented as
  equally certain as the measured free-length region.
- The bundled PA905 mass profile is estimated rather than measured.
- The Cast #1 result is qualitative; no requirement may claim that its
  simulated magnitudes match the reference cast quantitatively.
- A fitted rod's diameter is not part of the fit and must be supplied or
  defaulted separately when air drag is used.
- Uploaded measurement sets and reusable fits may remain in shared temporary
  server storage beyond the submitting session; no fixed retention period is
  guaranteed.
- Air drag and damping are optional; disabling them must leave the corresponding
  forces inactive.

## Requirements

### Functional Requirements

- **FR-001**: The product MUST provide an installable Python library and a
  browser-based Streamlit application.
- **FR-002**: The product MUST provide the configurable 1-D forced
  brick-spring-car oscillator and display its response as plots, with optional
  reference comparison, event markers, and animation.
- **FR-003**: The product MUST provide a planar rod/line/leader continuum model
  with bending, tension, gravity, optional Reynolds-number air drag, optional
  Kelvin-Voigt material damping, and coupled subdomain junctions.
- **FR-004**: The continuum engine MUST implement the seven-field state and
  second-order staggered spatial discretisation described in the as-built
  model description, and MUST support the generalized-alpha time integration
  and nonlinear solution process described there.
- **FR-005**: The product MUST provide Cast #1 using the recorded-cast
  geometry, current fitted-by-eye rod-butt motion, forward hand translation,
  initial line layout, and measured chord/event references described above.
- **FR-006**: The Cast #1 interface MUST allow line weight, rod, rod stiffness
  scale, grid size, drag, damping, display options, and line-speed measurement
  position to be selected within the stated current bounds.
- **FR-007**: The Cast #1 simulation MUST run only on explicit user request;
  changing only the line-speed measurement position MUST NOT rerun it.
- **FR-008**: The rod tools MUST estimate swingweight from per-section
  measurements, assembled length, ferrule overlap, and the applicable
  reel-seat/grip assumption.
- **FR-009**: The rod tools MUST load and display the bundled fitted rods and
  allow comparison of their stiffness, mass, frequency, load, and bend-fit
  information.
- **FR-010**: The rod fitting workflow MUST accept both a rod-data zip archive
  and equivalent guided-form inputs, including bend-test frames and image
  calibration.
- **FR-011**: The rod fitting workflow MUST support quick and full presets,
  provide fit progress and diagnostics, export fitted rod data, and make the
  result available to relevant views for the current app session.
- **FR-012**: The product MUST include the three bundled fitted rods (PA905,
  XP590, TCR590) and the packaged Cast #1 rod/line/leader component data.
- **FR-013**: The library MUST provide public programmatic access to the
  simple model, FEM models and solvers, rod tools, and packaged-data loaders.
- **FR-014**: The FEM implementation MUST pass the six exact verification
  cases and the second-order spatial convergence checks.
- **FR-015**: The numerical FEM core MUST remain independent of plotting
  libraries; user-interface and plotting concerns MUST remain outside the
  numerical core.
- **FR-016**: Packaged component and fitted-rod files MUST be included in
  distributions; the large measurement assets under repository `assets/`
  MUST remain non-packaged reference inputs.
- **FR-017**: The product MUST preserve provenance, units, and fit assumptions
  in measurement and fitted-rod artifacts sufficiently to interpret and
  reproduce the generated profiles.
- **FR-018**: The product MUST provide a publicly hosted Streamlit application.
  Pull requests MUST run validation or preview work without replacing the
  public app; a merge into `main` MUST publish the updated public app.
- **FR-019**: The app MUST cache uploaded rod datasets and reusable fits in
  shared temporary server storage keyed by content and fit settings, allowing
  matching work to be reused across sessions. The product MUST NOT promise a
  fixed retention period for this temporary cache.

### Key Entities

- **Simulation configuration**: model selection and its physical, numerical,
  and display parameters.
- **Simulation result**: time history of model fields and derived positions,
  speeds, events, and comparisons used by the UI.
- **Tackle component**: rod, line, or leader metadata and spatial profiles
  joined into a rig.
- **Rod section measurement**: section name, mass, length, and balance point,
  with assembled length and finished-rod status.
- **Rod measurement set**: rod metadata, clamp and image calibration, static
  bend frames, optional background image, frequency observations, CCS data,
  section measurements, and frame inclusion choices.
- **Fitted rod**: rod metadata, bending-stiffness and mass profiles, fitted
  parameters, diagnostics, and provenance, exportable for later loading.

## Future Plans (Non-Binding Backlog)

The items below are the ideas recorded in `docs/planned.rst` as of this
baseline. They are not shipped behavior, acceptance requirements, or a
committed sequence of work. The source backlog has no dates or priorities.

### Rod characterization

- Measure PA905 section masses and actual rod diameters; fitted rods currently
  borrow a diameter taper for drag.
- Estimate uncertainty in fitted profiles and make use of PA905 butt-rotation
  image sets.
- Model the test mount, whose zero-load frames sag more than the current model
  allows.
- Retune the Cast #1 stroke for measured rods rather than the stiffer tabulated
  rod.
- Consider derived rod parameters such as action, balance point, and
  recommended line weight.

### Tackle modeling

- Add first-class tapered mass and diameter profiles for fly lines and leaders.
- Extend the current rod/line/leader assembly with dedicated coupled
  leader/fly behavior to support realistic loop unrolling.
- Add a spherical fly terminal point-mass and drag boundary condition.

### Casting dynamics and measurement

- Import casting-stroke data to drive simulations, sourced from video
  measurement, motion-sensor systems, or user-defined configuration/graphical
  input.
- Extract hand path and rod angle, rotation, or motion from high-speed video.
- Compute caster hand force and torque, and integrate them to obtain work.
- Model hauling by coupling the free-hand line pull to the line subdomain.
- Develop a tuned and validated quantitative cast model.

### Outputs and tooling

- Export simulated trajectories, line shapes, and derived quantities to common
  formats such as CSV.
- Compute model energy and work balances.
- Report kinetic, elastic, and gravitational potential energy by component
  over the cast.

## Success Criteria

### Measurable Outcomes

- **SC-001**: The baseline describes all three current application areas and
  the independent Python library surface, including user inputs, outputs, and
  observable behavior.
- **SC-002**: The six independent user journeys and 19 functional
  requirements cover the current capabilities named in the README and
  user-facing documentation.
- **SC-003**: A rebuilt implementation can be assessed against the six user
  journeys, six exact FEM verification cases, and the second-order spatial
  convergence check.
- **SC-004**: All four future-work categories and their listed items from the
  source backlog appear under a clearly non-binding section and are not
  presented as current functionality.
- **SC-005**: Reviewers can distinguish current behavior, known limitations,
  and future ideas in every section of this baseline without treating
  as-built implementation context as a new design mandate.
- **SC-006**: The public app is reachable at its hosted URL; pull requests run
  validation or preview work without replacing it, and merges into `main`
  publish the updated app.
- **SC-007**: Repeating a fit with the same measurement content and preset can
  reuse the cached fit across sessions, and the specification states that
  temporary cache retention has no fixed guarantee.

## Assumptions

- The target baseline is the repository state reviewed on 2026-10-19; this
  document does not define a new release or promise backward compatibility
  beyond behavior described here.
- Current implementation and detailed documentation are the evidence for
  as-built behavior. Where evidence is incomplete, the uncertainty is stated
  rather than filled with an invented requirement.
- No product-level maximum archive size or bend-frame count is specified;
  effective upload and processing limits depend on the hosting environment.
- The future backlog is captured for planning continuity only. Dates,
  priorities, scope, and implementation choices will be defined in separate
  feature specifications when work is selected.
- The existing documentation, tests, and data are required companion
  references for detailed physics, equations, schemas, and numerical
  assumptions; this baseline links to them rather than duplicating every
  derivation.
