Continuum (FEM) core engine
=============================
A continuum, finite-element-style model of a single fly-line / rod
subdomain, based on Ekander, Perkins & Richards (*Sports Engineering*,
2025) and the theory pages at `willmanco.se <https://www.willmanco.se>`_.

Overview
------------------------------
The :mod:`flycastsim.fem` subpackage solves the planar continuum equations
for a slender, (in)extensible beam/line.  Each material point carries seven
fields,

* tangential and normal velocities ``u_s``, ``u_n``,
* tangential and normal internal forces ``F_s`` (tension), ``F_n`` (shear),
* tangent angle ``phi`` (measured from the ``+x`` axis),
* curvature ``nu_z = d phi / ds`` and its gradient ``Gamma_z = d nu_z / ds``,

governed by the kinematic constraints, the tangential/normal momentum
balances, and an Euler-Bernoulli / Kelvin-Voigt moment relation.  The current
core engine includes **bending, tension and gravity**, plus the optional
**Reynolds-number air drag** and **Kelvin-Voigt material damping**;
multi-subdomain coupling and the fly terminal condition remain scaffolded for
later extension.

Numerics
------------------------------
* **Space** -- a staggered finite-difference discretisation on a 1-D
  arc-length grid (the six first-order spatial equations are collocated at
  cell midpoints, the algebraic moment relation at the nodes).
* **Time** -- a first-order generalised-alpha integrator with a tunable
  spectral radius ``rho_inf``, Newton-Raphson iteration each step, and a
  sparse (2-colour) finite-difference Jacobian solved with ``scipy`` sparse LU.

Boundary conditions
------------------------------
Exactly one Dirichlet condition is supplied per spatially-differentiated
field (``u_s``, ``u_n``, ``F_s``, ``F_n``, ``phi``, ``nu_z``), distributed
across the two ends, e.g. a clamped end fixes ``u_s = u_n = 0`` and ``phi``,
while a free / roller end prescribes forces such as ``F_s`` and ``F_n``.

Verification
------------------------------
The engine is validated against the six exact test cases from the paper's
verification suite (see ``tests/unit/test_fem_verification.py``):

#. Static hanging chain (catenary)
#. Static towed line (catenary)
#. Static non-uniform beam
#. Dynamic oscillating beam
#. Dynamic hanging chain
#. Dynamic travelling wave

and a Richardson self-convergence check confirming the second-order spatial
accuracy.

Theory coverage and deviations
------------------------------
The implementation follows the source model of Ekander, Perkins & Richards
(*Sports Engineering* 2025) and the `willmanco.se <https://www.willmanco.se>`_
*Theory* / *Verification* pages.  The table below maps the elements of that
model to their status in the current engine.

.. list-table::
   :header-rows: 1
   :widths: 38 18 44

   * - Model element (source)
     - Status
     - Where / notes
   * - Seven coupled fields ``u_s, u_n, F_s, F_n, phi, nu_z, Gamma_z``
     - Implemented
     - :mod:`flycastsim.fem.state`
   * - Kinematic constraints (eqs 1-2)
     - Implemented
     - ``operators.residual`` (``EQ_KIN_S/N``)
   * - Newton momentum balances (eqs 3-4), with gravity
     - Implemented
     - ``operators.residual`` (``EQ_MOM_S/N``)
   * - Moment/curvature relation (eqs 7-9), incl. Kelvin-Voigt ``eta`` term
     - Implemented
     - ``operators.residual`` (nodal row); material damping enabled via
       non-zero ``eta`` on the sample casts
   * - Reynolds-dependent air drag (eqs 5-6)
     - Implemented
     - :func:`flycastsim.fem.reynolds_drag` (form + friction drag); enabled
       via ``air_drag=True`` on :func:`flycastsim.fem.simulate_cast` /
       :func:`flycastsim.fem.simulate_cast1`
   * - External handle BC ``u_s, u_n, phi(t)`` prescribed in time
     - Implemented
     - ``operators.BoundaryConditions``; used by
       :func:`flycastsim.fem.simulate_cast`
   * - Spherical-fly terminal BC (mass + drag, eqs after 11)
     - Planned
     - the sample cast uses a free tip (``F_s = F_n = 0``) instead
   * - Internal BCs between subdomains (eqs 10-11)
     - Planned
     - single-subdomain engine only
   * - Generalised-alpha time integration (2nd order)
     - Implemented
     - :mod:`flycastsim.fem.genalpha`
   * - Newton-Raphson with Jacobian (2nd order in space)
     - Implemented
     - :mod:`flycastsim.fem.solver`
   * - Position reconstruction ``x = integral e_s ds``
     - Implemented
     - :mod:`flycastsim.fem.coords`
   * - Energies and work outputs (eqs 14-20)
     - Planned
     - not computed yet
   * - Multi-subdomain assembly (rod + line + leader + fly)
     - Planned
     - :class:`~flycastsim.fem.domain.Subdomain` models one segment

**Deliberate deviations from the source description.**

* *Spatial scheme.* The *Theory* page specifies a **centered** spatial
  discretisation (the paper cites ref. [16]).  We instead use a compact
  **staggered** (cell-midpoint) scheme, because collocated centered
  differences admit a spurious odd/even ("checkerboard") mode in this mixed
  force/velocity system.  The staggered scheme remains second-order accurate,
  as confirmed by the convergence test.
* *Linear solve.* The paper describes a **banded** matrix solve.  We assemble
  the same sparsity with a two-colour (even/odd node) finite-difference
  Jacobian and solve it with a sparse direct (SuperLU) factorisation -- an
  equivalent, implementation-level choice.

Sources
------------------------------
* H. Ekander, N. C. Perkins, B. Richards, *Development of a simulation model
  for fly casting and application to overhead casting*, Sports Engineering
  (2025) 28:2 -- ``data/articlesportsengineeringrev4d.pdf``.
* The willmanco.se *Theory*, *Basics* and *Verification* pages, archived under
  ``data/willmanco.se/``.
* G. Løvoll and J. Borger, *The Rod & The Cast* (FlyFisher, 2006; web version
  archived under ``data/sexyloops.com/``) — source of the Cast #1 reference data
  and the uploaded high-speed footage (``data/videos/``).

Example
------------------------------
Free vibration of a simply-supported beam, recovering the first natural
frequency ``omega = (pi/L)^2 sqrt(EI/m)``:

.. code-block:: python

    import numpy as np
    from flycastsim import fem
    from flycastsim.fem import state as st
    from flycastsim.fem.operators import BoundaryConditions
    from flycastsim.fem.coords import positions

    L, N, EI, m = 1.0, 81, 1.0, 1.0
    dom = fem.uniform_beam(L, N, m=m, EI=EI)
    s = dom.s

    bc = BoundaryConditions()
    bc.dirichlet(0, st.U_S, 0.0).dirichlet(0, st.U_N, 0.0).dirichlet(0, st.NU_Z, 0.0)
    bc.dirichlet(N - 1, st.F_S, 0.0).dirichlet(N - 1, st.U_N, 0.0).dirichlet(N - 1, st.NU_Z, 0.0)

    x0 = st.zeros(N)
    x0.phi[:] = 1e-3 * (np.pi / L) * np.cos(np.pi * s / L)
    x0.nu_z[:] = np.gradient(x0.phi, s)
    x0.Gamma_z[:] = np.gradient(x0.nu_z, s)

    omega = (np.pi / L) ** 2 * np.sqrt(EI / m)
    period = 2 * np.pi / omega
    res = fem.integrate(dom, bc, x0.to_vector(), t_span=(0.0, 4 * period),
                        dt=period / 100, gravity=0.0, rho_inf=0.95)

    # reconstruct the line shape at the final step
    x, y = positions(res.fields_at(-1).phi, s)

Sample fly cast
------------------------------
A higher-level, qualitative demonstration is provided by
:func:`flycastsim.fem.simulate_cast`, which drives a tapered rod-plus-line
beam with a rotating casting stroke (a time-varying handle boundary
condition) under gravity and returns the line shape at every time step:

.. code-block:: python

    import numpy as np
    from flycastsim.fem import simulate_cast
    from flycastsim import animate_fly_cast, plot_cast_snapshots

    t, X, Y, s = simulate_cast(
        length=3.0, n_nodes=61,
        EI_butt=50.0, taper=0.6, EI_line=0.02, mass=0.05,
        sweep=np.deg2rad(120.0), t_stroke=0.4, t_end=0.9,
        dt=2e-3, gravity=9.81)

    fig = animate_fly_cast(t, X, Y)        # Plotly animation
    snaps = plot_cast_snapshots(t, X, Y)   # stroboscopic line shapes

This powers the *Sample fly cast* section of the Streamlit app, where the
stroke and rod/line properties can be adjusted interactively.  Optional
**air drag** (``air_drag=True``) and **material damping** (``eta``) let the line
shed energy, but it remains a *qualitative* demonstration: the line is
inextensible and modelled as a single segment, and the handle is a pure
rotation about a fixed pivot — a fully realistic loop unrolling additionally
needs the multi-segment rod+line+leader+fly model and a translating handle.


Reproducing Cast #1 of "The Rod & The Cast"
-------------------------------------------
:func:`flycastsim.fem.simulate_cast1` configures the engine to reproduce a
*real* recorded cast: **Cast #1** from Løvoll & Borger's study *The Rod & The
Cast* (the uploaded ``cast01_m1`` high-speed clip — caster Mathias Lilleheim,
**T&T Paradigm 9 ft 5-wt**, recorded at ~500 fps).  The rod is driven by the
rod-butt tangent angle **fitted to the footage** (:mod:`flycastsim.fem._cast1_data`):
an overhead delivery that starts **up and back** (second quadrant) and sweeps
**clockwise** down toward the vertical as the loop forms — the rod tip stays
elevated throughout.  The rod butt (the casting hand) is also **translated
forward** (a haul) while it rotates, not pinned to a fixed pivot.  The full
**~12.7 m line + leader** is modelled and **starts laid out behind** the caster
tilted **15° below horizontal** (line end lowest, rod tip highest; see
:func:`flycastsim.fem.cast1_initial_phi`), so the line **loads the rod** through
the stroke.  The line mass is set by the chosen **AFTM line weight** (heavier
line loads the rod more).  The simulated rod **chord
length** (the straight-line distance from the handle to the rod tip) is compared
against the measured curve.  Time is referenced to **RSP** (Rod Straight
Position), where ``t = 0``.

.. code-block:: python

    from flycastsim.fem import simulate_cast1
    from flycastsim import (animate_fly_cast, plot_cast_snapshots,
                            plot_chord_comparison, load_cast1_frames)

    t, X, Y, s, chord, rod_tip = simulate_cast1()   # t is relative to RSP

    anim = animate_fly_cast(t, X, Y, rod_tip_index=rod_tip)  # colour-coded
    cmp = plot_chord_comparison(t, chord)           # sim vs. measured chord
    frames = load_cast1_frames()                    # real event-frame strip

Passing ``rod_tip_index`` colour-codes the animation and snapshots, drawing the
**rod** and the **fly line** as separate coloured traces.

This powers the *Cast #1 — The Rod & The Cast* mode of the dashboard's sample-
cast section, which shows the four real event frames (MAV/MCL/RSP/MCF, extracted
from the footage to ``assets/cast1/``) beside the simulated rod and the chord
comparison.  All four events sit in the first ~0.69 s of real time (frames
243–346 at ~500 fps, RSP = frame 317) — i.e. within the first 12 s of the clip
at normal 30 fps playback.

**What is and isn't matched.**  Air drag can now be enabled
(``air_drag=True``), and the full ~12.7 m line + leader is modelled and laid out
**behind** the caster tilted 15° below horizontal at the start (line end lowest,
rod tip highest).  The **AFTM line weight** is adjustable (heavier line loads the
rod more).  A little **line-only material damping**
(:data:`flycastsim.fem.CAST1_LINE_ETA`) keeps that floppy tilted layout
numerically stable while the **rod stays elastic**.  The driving rod-butt
motion is still an **idealized angle sweep fitted by eye** to the footage, with a
simple forward haul translation.  Because the line is a single floppy subdomain
(no internal leader/fly boundaries), it cannot unroll into a crisp loop: the
heavy tilted line **loads the rod** deeply and the rod rebounds slightly after
the stop — a documented single-subdomain limitation.  The comparison
therefore remains *qualitative*: the rod geometry (up-back start, clockwise
loading sweep, tip staying elevated) and the loading/straightening of the chord
are reproduced, not exact magnitudes.  The full floppy line is
**ill-conditioned on coarse grids**, so ``n_nodes >= 101`` is required (and is
the default).  The labelled event times and tip speeds (Table 1) are exact
published values; see :mod:`flycastsim.fem._cast1_data` for full provenance.
