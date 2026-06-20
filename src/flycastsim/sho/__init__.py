"""Simple 1-D (toy) fly-casting model: a forced harmonic oscillator.

This subpackage implements the simplistic *brick-spring-car* casting model,
where the fly line is replaced by a "brick" towed along a frictionless surface
by a "car" connected through a linear spring.  The car motion mimics rod
leverage and the spring mimics the elastic bending/un-bending of the rod, so
the system is, in essence, a forced harmonic oscillator.

* :mod:`flycastsim.sho.model` solves the model numerically with a SciPy ODE
  integrator (:func:`simple_sim`).
* :mod:`flycastsim.sho.helpers` provides Plotly plotting and animation helpers
  (:func:`plot_brick_spring`, :func:`animate_brick_spring`,
  :class:`BrickSpringAnim`).

The original Matlab implementation is kept for reference under
``flycastsim/sho/matlab/``.
"""

from . import helpers, model
from .model import dydt, simple_sim
from .helpers import (BrickSpringAnim, animate_brick_spring, plot_brick_spring)

__all__ = [
    "model",
    "helpers",
    "dydt",
    "simple_sim",
    "plot_brick_spring",
    "animate_brick_spring",
    "BrickSpringAnim",
]
