Rod parameters — Stiffness and mass profile (design note)
==========================================================
**Status: design note, under implementation.**  This page records the agreed
design for estimating a rod's bending-stiffness profile :math:`EI(s)` and
linear mass density :math:`\mu(s)` from measurements.  It is updated as the
pieces land; the implementation status of each part is listed at the end.

The goal is a *measured* rod profile in the ``s_m, m_kg_per_m, EI_Nm2`` format
read by :mod:`flycastsim.fem.components` (e.g. ``data/components/cast1/rod.csv``,
today a hand-tabulated guess), replacing guessed tapers in the continuum
engine.  It covers the backlog items *stiffness (EI) profile from static bend
tests* and *mass distribution* in :doc:`planned`.

Notation
------------------------------
* :math:`s` — arc length from the rod **butt** [m]; :math:`L` the assembled
  rod length; :math:`s_c` the clamp point (≈ 0.25 m for all data sets).
* :math:`\theta(s)` — angle of the rod tangent above the horizontal.
* :math:`M(s)` — bending moment, :math:`EI\,\theta' = M`.
* :math:`P = m_{tip} g` — tip load; :math:`g = 9.81\ \mathrm{m/s^2}`.

Measurement data
------------------------------
Each measured rod has a folder ``assets/<ROD>/`` with a ``rod.yaml``
(schema ``flycastsim.rod.measurement/1``) collecting all inputs and
calibration.  Values that are unknown are ``null`` and are either fitted or
left out of the fit.

``rod``
    Assembled length and per-section mass, length and balance point (the
    :class:`~flycastsim.rod.swingweight.RodSection` inputs) plus ferrule
    overlap.  XP590 and TCR590 come from the MOI log; PA905 has none yet.
``mount``
    Clamp position :math:`s_c` and clamp (butt) angle.
``calibration``
    Pixel scale is taken from the rod length: the traced clamp-to-tip arc
    length equals :math:`L - s_c` (the old ``lscale`` does not match the
    frames and is kept for reference only).  Optional tracked-marker
    positions and, for PA905, a plumb line drawn on the wall (gravity
    direction).
``static_bend``
    Image sequence with the tip load increased by a constant, *unknown* step
    :math:`\Delta m` per frame; frame 0 is zero added load (hook ignored).
``butt_rotation``
    PA905 only: fixed tip load of :math:`n` beads with the butt rotated
    through unmeasured angles.  Whether one bead equals :math:`\Delta m` is
    not confirmed, so the bead mass is a separate unknown.
``ccs``
    Common Cents System: the tip load ``ip_g`` giving a tip deflection of
    1/3 of the free length :math:`L - s_c`, and the action angle.
``frequency_test``
    Fundamental frequency vs. known tip mass, same clamp as the bend test.

Scale ambiguity
------------------------------
In the static tests every force is either the tip load or self-weight, so
scaling :math:`\Delta m`, :math:`\mu` and :math:`EI` together leaves all bend
shapes unchanged.  Absolute scale comes from data in known units: section
masses (when measured), the CCS load, and the frequency test's tip masses.
These also cross-check each other.

Parametrisation
------------------------------
Mass density :math:`\mu(s)`
    Linear within each section with jumps at the ferrules — the swingweight
    assumption (Løvoll & Angus 2008).  Two parameters per section are tied to
    the measured section mass and balance point through a penalty with
    measurement uncertainties (default ±0.2 g, ±5 mm), so the fit may adjust
    them slightly.  Without section data a weak smoothness prior is used.
Stiffness :math:`EI(s)`
    Cubic B-spline in :math:`\log EI` on 6–10 knots spread over the free
    length, constrained **non-increasing** from butt to tip: coefficients
    :math:`c_{i+1} = c_i - e^{b_i}`, which makes the spline monotone
    (variation-diminishing property of B-splines) while the fit stays
    unconstrained.  A small curvature penalty controls smoothness.
    Behind the clamp (:math:`s < s_c`), where no test sees the rod,
    :math:`EI` is held constant at :math:`EI(s_c)`.

Forward models
------------------------------
Static large-deflection bend (:mod:`flycastsim.rod.elastica`)
    Planar inextensible Euler–Bernoulli rod (the *elastica*), clamped at
    :math:`s_c` at angle :math:`\theta_c`, loaded by self-weight and a tip
    load:

    .. math::

        x' = \cos\theta,\quad y' = \sin\theta,\quad
        \theta' = \frac{M}{EI(s)},\quad M' = W(s)\cos\theta,

    with :math:`W(s) = P + g\int_s^L \mu\,d\sigma` the weight outboard of
    :math:`s`, and boundary conditions :math:`x = y = 0,\ \theta = \theta_c`
    at the clamp and :math:`M = 0` at the tip.  Solved as a two-point
    boundary-value problem (``scipy.integrate.solve_bvp``); load sequences
    are solved in order with warm starts, and difficult loads by
    continuation.  Deliberately static and shear-free, unlike the dynamic
    continuum engine in :mod:`flycastsim.fem`.
Tip-mass frequency
    Lowest bending mode of the clamped rod with a tip point mass (linear
    Euler–Bernoulli eigenproblem, finite differences).  Gravity pre-stress
    is neglected initially.  As a quick check, :math:`1/f^2` vs. tip mass is
    nearly linear for all three rods.
CCS
    The elastica tip deflection at load ``ip_g`` must equal 1/3 of the free
    length.
Swingweight
    Section masses and balance points from :math:`\mu(s)`, compared with the
    measured values.

Image pipeline (:mod:`flycastsim.rod.imaging`)
-----------------------------------------------
Images are the primary data; tracked markers are optional.  Raw frames (dark
rod on a light wall) and background-subtracted frames (bright rod on black)
both go through the same path:

#. optional subtraction of a background frame, then a morphological top-hat
   high-pass filter; polarity is normalised so the rod is bright;
#. ridge following from the clamp: at each step a short intensity profile
   across the rod gives a sub-pixel centre (intensity-weighted centroid),
   then a step of a few pixels along the local tangent; stop where contrast
   drops to background at the tip;
#. robust smoothing along the curve to reject guides, ferrules, wraps and
   drawn annotations.

Fit (:mod:`flycastsim.rod.profile_fit`)
----------------------------------------
Joint ``scipy.optimize.least_squares`` over all data:

* **static frames**: distance from each extracted centre-line point to the
  modelled curve (no point correspondence needed, the model is
  inextensible), plus a tip-position term; tracked markers, when present,
  add point terms with their arc lengths fitted once for all frames;
* **frequency** and **CCS** residuals;
* **swingweight** penalty on section masses and balance points;
* **smoothness** penalty on :math:`\log EI`.

Unknowns: spline coefficients, :math:`\Delta m`, bead mass (PA905), per-image
butt angles for the rotation sets (initialised from the rod tangent at the
clamp), an image transform per data set (clamp pixel position, scale, camera
roll — the roll is separable from the clamp angle because heavily loaded
frames show the gravity direction), and the :math:`\mu` parameters.

Output: a rod CSV for :mod:`flycastsim.fem.components`, plus Plotly plots of
fit residuals and profiles in :mod:`flycastsim.rod.helpers`.

Implementation plan
------------------------------
New modules in :mod:`flycastsim.rod`, in build order:

#. ``elastica.py`` — static solver; verified against small-deflection beam
   theory (uniform and tapered, tip load and self-weight) and the exact
   large-deflection tip-load cantilever (Bisshopp & Drucker 1945).
#. ``vibration.py`` — tip-mass frequency; verified against the uniform
   cantilever eigenvalue :math:`\beta_1 L = 1.8751`.
#. ``profile_fit.py`` — parametrisations and joint fit; verified by
   recovering a known synthetic profile.
#. ``imaging.py`` — centre-line extraction; verified on synthetic raw-style
   and background-subtracted images.
#. ``measurement.py`` — ``rod.yaml`` loader (adds the ``pyyaml``
   dependency).
#. Example notebook running PA905 end to end, and docs in :doc:`rod`.

.. list-table:: Status
   :header-rows: 1

   * - Part
     - Status
   * - Measurement configs (``assets/*/rod.yaml``)
     - done
   * - Elastica solver + verification tests
     - in progress
   * - Frequency model
     - planned
   * - Profile fit
     - planned
   * - Image pipeline
     - planned
   * - Loader, example notebook, docs
     - planned

Sources
------------------------------
* K. E. Bisshopp and D. C. Drucker, *Large deflection of cantilever beams*,
  Quarterly of Applied Mathematics **3** (1945) 272–275.
* R. Frisch-Fay, *Flexible Bars*, Butterworths (1962).
* G. Løvoll and M. Angus, *Measuring fly rod "swingweight"* (2008).
* W. Hanneman, *Common Cents System* (CCS) for fly-rod characterisation.
