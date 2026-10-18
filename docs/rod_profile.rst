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
    unconstrained.  A small curvature penalty (second divided differences of
    the coefficients over their Greville abscissae, zero for an exponential
    taper) controls smoothness.  Parameter bounds keep trial steps
    physical: each coefficient drop is at most ``max_log_step``, and section
    balance points stay in :math:`[l/3, 2l/3]` where the linear density is
    non-negative.
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
    continuation.  The fit uses a fixed-mesh variant
    (``solve_cantilever_fd``: trapezoidal rule on 200 segments, Newton with
    a sparse analytic Jacobian, ~2–3 ms per warm-started solve) whose result
    is a smooth function of the parameters, as the finite-difference
    Jacobian of the fit requires; it agrees with ``solve_bvp`` to ~5 µm at
    the tip.  Deliberately static and shear-free, unlike the dynamic
    continuum engine in :mod:`flycastsim.fem`.
Tip-mass frequency (:mod:`flycastsim.rod.vibration`)
    Lowest bending mode of the clamped rod with a tip point mass: linear
    Euler–Bernoulli eigenproblem discretised with cubic Hermite beam
    elements (:math:`O(h^4)` convergence), with ferrules as optional mesh
    breakpoints.  Static sag and gravity pre-stress are neglected.  As a quick check, :math:`1/f^2` vs. tip mass is
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
both go through the same path (``extract_centerline``):

#. ``ridge_image``: with a background frame, the absolute difference
   ``|image - background|`` (the blank has a bright specular highlight on its
   upper side and a dark lower side, and only using the dark part biased the
   centre by 2–3 px); then a morphological top-hat (rod narrower than the
   structuring element) with automatic polarity, which removes uneven
   lighting and large objects such as cabinets;
#. ``trace_centerline``: ridge following from a start point just outboard of
   the clamp.  Each step takes a profile across the rod and follows the
   ridge peak *closest to the predicted position* among peaks above half the
   local rod strength, with the sub-pixel centre from the intensity-weighted
   centroid around it; larger sideways jumps count as gaps, so drawn labels
   and marker dots beside the rod are not followed.  The trace stops when
   the strength fades below a fraction of its running median (so the
   thinning tip is followed), and the tip is placed at half the local
   contrast along the end tangent;
#. a sharp, persistent **kink** in the last third of the trace ends the rod:
   the line to the load hanging from the tip, or a label drawn beyond it,
   continues at an angle, and the tip is put at the kink;
#. ``reject_outliers``: points deviating from a running median of their
   neighbours (guides, wraps, ferrules) are dropped.

On synthetic frames (tapered Gaussian rod, guide ticks, labels, lighting
gradients, a large dark object, noise) the centre line is within 0.3 px RMS
and the tip within 1.5 px.  On the PA905 frames the trace agrees with the
hand-tracked markers to their ~3 px precision; in the annotated frames the
foot of a drawn label can lie in line with the rod just past the tip, so raw
frames are preferred where the tip matters.

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

Numerical notes from the synthetic tests:

* :math:`EI` right at the tip is unobservable (the bending moment vanishes
  there), so the fitted profile is only trusted up to ~0.3 m from the tip.
* The fit is ill-conditioned: it needs tight tolerances
  (``xtol = ftol = 1e-10``) and a relative finite-difference step of
  ``1e-5``; the default step (~1.5e-8) amplifies residual round-off and
  stalls the fit.
* Too few spline coefficients bias the whole profile: with 0.5 mm point
  accuracy, 6 coefficients could not follow a realistic taper while 7 did
  (0.1 % error over the free length).

Implementation plan
------------------------------
New modules in :mod:`flycastsim.rod`, in build order:

#. ``elastica.py`` — static solver; verified against small-deflection beam
   theory (uniform and tapered, tip load and self-weight) and the exact
   large-deflection tip-load cantilever (Bisshopp & Drucker 1945).
#. ``vibration.py`` — tip-mass frequency; verified against the uniform
   cantilever modes (:math:`\beta_n L = 1.8751, 4.6941`), the exact
   tip-mass frequency equation and the massless-rod spring limit.
#. ``profile_fit.py`` — parametrisations and joint fit; verified by
   recovering a known synthetic profile.
#. ``imaging.py`` — centre-line extraction; verified on synthetic raw-style
   and background-subtracted images and on PA905 frames against the
   hand-tracked markers.
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
     - done
   * - Frequency model + verification tests
     - done
   * - Profile fit: parametrisations, residuals, joint fit (physical
       coordinates) + synthetic recovery test
     - done
   * - Profile fit: image transform (scale, clamp position, camera roll),
       tracked markers, butt-rotation sets, uncertainty estimates
     - planned
   * - Image pipeline + synthetic and PA905 tests
     - done
   * - Loader, example notebook, docs
     - planned

Sources
------------------------------
* K. E. Bisshopp and D. C. Drucker, *Large deflection of cantilever beams*,
  Quarterly of Applied Mathematics **3** (1945) 272–275.
* R. Frisch-Fay, *Flexible Bars*, Butterworths (1962).
* G. Løvoll and M. Angus, *Measuring fly rod "swingweight"* (2008).
* W. Hanneman, *Common Cents System* (CCS) for fly-rod characterisation.
