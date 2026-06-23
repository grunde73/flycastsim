"""Finite-element (continuum) fly-casting simulation engine.

This subpackage implements the 2-D continuum model of Ekander, Perkins &
Richards (*Sports Engineering* 2025).  The current core engine solves a
single beam/line subdomain with bending, tension and gravity, using

* a **staggered** (cell-midpoint) second-order finite-difference spatial
  discretisation (:mod:`flycastsim.fem.operators`).  The paper / willmanco
  *Theory* page specify a *centered* scheme; we deviate to a compact
  staggered scheme because collocated centered differences admit a spurious
  odd/even ("checkerboard") mode in this mixed force/velocity system.  The
  staggered scheme is still second-order accurate (verified by the test
  suite);
* a generalised-alpha time integrator with Newton-Raphson iteration and a
  **sparse, two-colour finite-difference Jacobian** solved with SuperLU
  (:mod:`flycastsim.fem.genalpha`, :mod:`flycastsim.fem.solver`).  The paper
  refers to a banded matrix; the sparse colouring is an equivalent,
  implementation-level choice.

The bending/moment relation carries the Kelvin-Voigt material relaxation term
(``eta``), and the residual applies an optional air-drag force.  The
Reynolds-number air-drag law (:mod:`flycastsim.fem.drag`, eqs 5-6) and
Kelvin-Voigt material damping are now implemented and can be enabled on the
sample casts.  **Multi-subdomain coupling** (rod + fly line + leader, joined at
pinned/welded junctions) is implemented in
:mod:`flycastsim.fem.multidomain` and used by the Cast #1 reproduction.  The
spherical-fly terminal boundary condition and energy/work outputs remain
planned extensions.  See the *Theory coverage* section of the documentation
for a full mapping to the source model.
"""

from . import (analytic, components, coords, domain, drag, multidomain,
               operators, solver, state)
from .cast import (casting_stroke, fly_cast_domain, simulate_cast,
                   cast1_domain, cast1_stroke, chord_length, tip_deflection,
                   simulate_cast1,
                   cast1_initial_phi, cast1_rod_tip_index, cast1_chord_base_index,
                   CAST1_LINE_ETA,
                   CAST1_LINE_INIT_DEG, CAST1_LINE_OUT, CAST1_ROD_LENGTH,
                   CAST1_CHORD_BASE_S, CAST1_RIG)
from .components import (Component, load_component, load_rig,
                         bundled_rig_path, copy_example_rig)
from .coords import (positions, positions_from_fields, positions_multi,
                     tension, node_speed, node_index_from_tip,
                     rigid_lever_tip, rigid_lever_speed)
from .domain import Subdomain, chain, uniform_beam
from .drag import reynolds_drag
from .genalpha import GenAlphaResult, integrate
from .multidomain import Junction, MultiDomain
from .operators import BoundaryConditions, BoundaryRow
from .solver import NewtonResult, solve_static, solve_static_multi
from .state import Fields

__all__ = [
    "analytic",
    "components",
    "coords",
    "domain",
    "drag",
    "multidomain",
    "operators",
    "solver",
    "state",
    "Subdomain",
    "uniform_beam",
    "chain",
    "Component",
    "load_component",
    "load_rig",
    "bundled_rig_path",
    "copy_example_rig",
    "Junction",
    "MultiDomain",
    "reynolds_drag",
    "BoundaryConditions",
    "BoundaryRow",
    "Fields",
    "NewtonResult",
    "solve_static",
    "solve_static_multi",
    "GenAlphaResult",
    "integrate",
    "positions",
    "positions_from_fields",
    "positions_multi",
    "tension",
    "node_speed",
    "node_index_from_tip",
    "rigid_lever_tip",
    "rigid_lever_speed",
    "casting_stroke",
    "fly_cast_domain",
    "simulate_cast",
    "cast1_domain",
    "cast1_stroke",
    "cast1_initial_phi",
    "cast1_rod_tip_index",
    "cast1_chord_base_index",
    "CAST1_LINE_ETA",
    "CAST1_LINE_INIT_DEG",
    "CAST1_LINE_OUT",
    "CAST1_ROD_LENGTH",
    "CAST1_CHORD_BASE_S",
    "CAST1_RIG",
    "chord_length",
    "tip_deflection",
    "simulate_cast1",
]
