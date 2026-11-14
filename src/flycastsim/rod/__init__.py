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
* :mod:`flycastsim.rod.data` loads the paper's worked-example rods and the
  bundled measured rods.
* :mod:`flycastsim.rod.elastica` solves the static large-deflection bend of a
  clamped rod (:func:`~flycastsim.rod.elastica.solve_cantilever`), the forward
  model for estimating a stiffness profile from static bend tests.
* :mod:`flycastsim.rod.vibration` gives the bending frequencies of a clamped
  rod with a tip mass (:func:`~flycastsim.rod.vibration.natural_frequencies`),
  the forward model for the tip-mass frequency test.
* :mod:`flycastsim.rod.profile_fit` fits the stiffness and mass profiles
  jointly to bend, frequency, CCS and section-mass data
  (:func:`~flycastsim.rod.profile_fit.fit_profile`).
* :mod:`flycastsim.rod.imaging` extracts the rod centre line and tip from
  bend-test frames (:func:`~flycastsim.rod.imaging.extract_centerline`).
* :mod:`flycastsim.rod.measurement` loads a rod's ``rod.yaml`` measurement
  data set (:func:`~flycastsim.rod.measurement.load_rod_measurement`) and
  fits it (:func:`~flycastsim.rod.measurement.fit_rod`).
* :mod:`flycastsim.rod.fitted` handles fitted rods, including the bundled
  ones (:func:`~flycastsim.rod.fitted.load_fitted_rods`).

The package is intentionally structured to grow into broader rod-parameter
handling (stiffness/EI tapers, action, recommended line weight, ...).
"""

from . import (
               data,
               elastica,
               fitted,
               helpers,
               imaging,
               measurement,
               profile_fit,
               swingweight,
               vibration,
)
from .data import (
               ExampleRod,
               MeasuredRod,
               MeasurementConsistency,
               check_consistency,
               load_example_rods,
               load_measured_rods,
               load_swingweight_csv,
)
from .elastica import (
               ElasticaError,
               ElasticaSolution,
               solve_cantilever,
               solve_cantilever_fd,
               solve_load_sequence,
)
from .fitted import FittedRod, load_fitted_rods
from .helpers import (
               fitted_rods_table,
               plot_bend_fit,
               plot_fitted_bend,
               plot_fitted_frequency,
               plot_fitted_loads,
               plot_fitted_profiles,
               plot_rod_profiles,
               plot_swingweight_contributions,
               trace_overlay,
)
from .imaging import CenterlineTrace, extract_centerline
from .measurement import (
               FIT_PRESETS,
               RodMeasurement,
               create_measurement,
               export_fit,
               fit_rod,
               load_rod_measurement,
)
from .profile_fit import (
               BendFrame,
               CCSData,
               FrequencyData,
               ImageTransform,
               MonotoneLogEI,
               ProfileFitProblem,
               ProfileFitResult,
               SectionMassModel,
               fit_profile,
)
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
from .vibration import frequency_vs_tip_mass, natural_frequencies

#: Convenience aliases for the estimator function.  The submodule
#: :mod:`flycastsim.rod.swingweight` keeps the ``swingweight`` *module* name, so
#: the callable is exposed here as :func:`compute_swingweight` (and
#: :func:`swingweight_fn`).
swingweight_fn = compute_swingweight

__all__ = [
               "FIT_PRESETS",
               "L_RG_DEFAULT",
               "BendFrame",
               "CCSData",
               "CenterlineTrace",
               "ElasticaError",
               "ElasticaSolution",
               "ExampleRod",
               "FittedRod",
               "FrequencyData",
               "ImageTransform",
               "MeasuredRod",
               "MeasurementConsistency",
               "MonotoneLogEI",
               "ProfileFitProblem",
               "ProfileFitResult",
               "ReelSeatGrip",
               "RodMeasurement",
               "RodSection",
               "SectionMassModel",
               "SectionResult",
               "SwingweightResult",
               "check_consistency",
               "compute_swingweight",
               "create_measurement",
               "data",
               "elastica",
               "export_fit",
               "extract_centerline",
               "fit_profile",
               "fit_rod",
               "fitted",
               "fitted_rods_table",
               "frequency_vs_tip_mass",
               "helpers",
               "imaging",
               "load_example_rods",
               "load_fitted_rods",
               "load_measured_rods",
               "load_rod_measurement",
               "load_swingweight_csv",
               "measurement",
               "natural_frequencies",
               "plot_bend_fit",
               "plot_fitted_bend",
               "plot_fitted_frequency",
               "plot_fitted_loads",
               "plot_fitted_profiles",
               "plot_rod_profiles",
               "plot_swingweight_contributions",
               "profile_fit",
               "reel_seat_grip_correction",
               "section_moi",
               "section_moi_about_cm",
               "solve_cantilever",
               "solve_cantilever_fd",
               "solve_load_sequence",
               "swingweight",
               "swingweight_fn",
               "trace_overlay",
               "vibration",
]
