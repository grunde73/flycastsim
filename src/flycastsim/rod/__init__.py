"""Fly-rod parameters: getting and setting up rod properties.

This subpackage collects tools for working with fly-rod parameters.  Its first
(currently only) feature is **swingweight** estimation -- the moment of inertia
of a multi-piece single-handed fly rod about an axis at the rod butt -- using
the method of Løvoll & Angus, *"Measuring fly rod swingweight"* (2008, bundled
as ``data/swingweight.pdf``, also at
https://www.sexyloops.com/articles/swingweight.pdf).

* :mod:`flycastsim.rod.swingweight` implements the calculation
  (:func:`~flycastsim.rod.swingweight.swingweight`,
  :class:`~flycastsim.rod.swingweight.RodSection`).
* :mod:`flycastsim.rod.helpers` provides a Plotly contribution plot.
* :mod:`flycastsim.rod.data` loads the paper's worked-example rods.
* :mod:`flycastsim.rod.elastica` solves the static large-deflection bend of a
  clamped rod (:func:`~flycastsim.rod.elastica.solve_cantilever`), the forward
  model for estimating a stiffness profile from static bend tests.
* :mod:`flycastsim.rod.vibration` gives the bending frequencies of a clamped
  rod with a tip mass (:func:`~flycastsim.rod.vibration.natural_frequencies`),
  the forward model for the tip-mass frequency test.

The package is intentionally structured to grow into broader rod-parameter
handling (stiffness/EI tapers, action, recommended line weight, ...).
"""

from . import data, elastica, helpers, swingweight, vibration
from .swingweight import (
    L_RG_DEFAULT,
    ReelSeatGrip,
    RodSection,
    SectionResult,
    SwingweightResult,
    reel_seat_grip_correction,
    section_moi,
    section_moi_about_cm,
)
from .swingweight import swingweight as compute_swingweight
from .helpers import plot_swingweight_contributions
from .data import ExampleRod, load_example_rods
from .elastica import (
    ElasticaError,
    ElasticaSolution,
    solve_cantilever,
    solve_load_sequence,
)
from .vibration import frequency_vs_tip_mass, natural_frequencies

#: Convenience aliases for the estimator function.  The submodule
#: :mod:`flycastsim.rod.swingweight` keeps the ``swingweight`` *module* name, so
#: the callable is exposed here as :func:`compute_swingweight` (and
#: :func:`swingweight_fn`).
swingweight_fn = compute_swingweight

__all__ = [
    "compute_swingweight",
    "swingweight_fn",
    "RodSection",
    "SectionResult",
    "SwingweightResult",
    "ReelSeatGrip",
    "section_moi",
    "section_moi_about_cm",
    "reel_seat_grip_correction",
    "L_RG_DEFAULT",
    "plot_swingweight_contributions",
    "ExampleRod",
    "load_example_rods",
    "ElasticaError",
    "ElasticaSolution",
    "solve_cantilever",
    "solve_load_sequence",
    "natural_frequencies",
    "frequency_vs_tip_mass",
    "data",
    "elastica",
    "helpers",
    "swingweight",
    "vibration",
]
