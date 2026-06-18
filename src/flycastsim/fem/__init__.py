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

The bending/moment relation already carries the Kelvin-Voigt material
relaxation term (``eta``), and the residual exposes an optional air-drag
hook, but no drag law and no material damping are exercised by the core
engine yet.  Reynolds-number-dependent air drag, the spherical-fly terminal
boundary condition, energy/work outputs and multi-subdomain coupling (rod +
fly line + leader + fly) are planned extensions.  See the *Theory coverage*
section of the documentation for a full mapping to the source model.
"""

from . import analytic, coords, domain, operators, solver, state
from .cast import (casting_stroke, fly_cast_domain, simulate_cast,
                   cast1_domain, cast1_stroke, chord_length, simulate_cast1)
from .coords import positions, positions_from_fields, tension
from .domain import Subdomain, chain, uniform_beam
from .genalpha import GenAlphaResult, integrate
from .operators import BoundaryConditions, BoundaryRow
from .solver import NewtonResult, solve_static
from .state import Fields

__all__ = [
    "analytic",
    "coords",
    "domain",
    "operators",
    "solver",
    "state",
    "Subdomain",
    "uniform_beam",
    "chain",
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
