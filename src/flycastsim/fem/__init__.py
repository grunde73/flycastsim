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
sample casts.  The spherical-fly terminal boundary condition, energy/work
outputs and multi-subdomain coupling (rod + fly line + leader + fly) remain
planned extensions.  See the *Theory coverage* section of the documentation
for a full mapping to the source model.
"""

from . import analytic, coords, domain, drag, operators, solver, state
from .cast import (casting_stroke, fly_cast_domain, simulate_cast,
                   cast1_domain, cast1_stroke, chord_length, simulate_cast1)
from .coords import positions, positions_from_fields, tension
from .domain import Subdomain, chain, uniform_beam
from .drag import reynolds_drag
from .genalpha import GenAlphaResult, integrate
from .operators import BoundaryConditions, BoundaryRow
from .solver import NewtonResult, solve_static
from .state import Fields

__all__ = [
    "analytic",
    "coords",
    "domain",
    "drag",
    "operators",
    "solver",
    "state",
    "Subdomain",
    "uniform_beam",
    "chain",
    "reynolds_drag",
    "BoundaryConditions",
    "BoundaryRow",
    "Fields",
    "NewtonResult",
    "solve_static",
    "GenAlphaResult",
    "integrate",
    "positions",
    "positions_from_fields",
    "tension",
    "casting_stroke",
    "fly_cast_domain",
    "simulate_cast",
    "cast1_domain",
    "cast1_stroke",
    "chord_length",
    "simulate_cast1",
]
