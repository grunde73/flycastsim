Rod parameters — Swingweight
============================
Tools for getting and setting up fly-rod parameters
(:mod:`flycastsim.rod`).  The first (currently only) feature estimates a
rod's **swingweight**: the moment of inertia (MOI) of a multi-piece
single-handed fly rod about an axis at the **butt** of the rod.

This implements the method of G. Løvoll and M. Angus, *Measuring fly rod
"swingweight"* (2008) — bundled as ``data/swingweight.pdf`` and available at
`sexyloops.com <https://www.sexyloops.com/articles/swingweight.pdf>`_.

Why swingweight?
------------------------------
Swingweight captures how a rod *feels* to swing far better than its bare
mass.  Mass out toward the tip matters much more than mass near the grip,
because MOI grows with the **square** of the distance to the axis of rotation.
Two rods of equal mass can feel very different if their mass is distributed
differently.

Formally, the swingweight is the MOI about the rod butt (``x = 0``),

.. math::

    I_s = \int_0^l \mu(x)\, x^2\, dx,

where :math:`\mu(x)` is the linear mass density (mass per unit length) a
distance ``x`` from the butt.

The model
------------------------------
The mass distribution :math:`\mu(x)` is not easily measured, so the paper
makes two assumptions allowing a non-destructive estimate from simple
measurements:

#. The mass density of **each section** decreases **linearly** with distance
   from the thick (butt) end of that section.
#. The reel seat and grip are modelled as a thin uniform cylinder, so the
   butt-section *blank* mass centre can be inferred from the section above it.

For a section of mass :math:`m_{sec}`, length :math:`l_{sec}` and balance
point :math:`x_{cm}` (distance from the section's thick end to its mass
centre), the MOI about the rod-butt axis is (paper eq. 1)

.. math::

    I_{sec} = m_{sec} l_{sec}^2\left(\frac{x_{cm}}{l_{sec}} - \frac16\right)
              - m_{sec} x_{cm}^2 + m_{sec} d_{sec}^2,

where the first two terms are the MOI about the section's own mass centre and
the last term is the parallel-axis shift to the rod butt by :math:`d_{sec}`
(distance from the rod butt to that section's balance point).  The
:math:`d_{sec}` values are accumulated section by section while removing the
**ferrule overlap** (paper eqs. 2–5), and the butt section of a finished rod
gets a dedicated **reel-seat / grip correction** (eqs. 6–9, with an assumed
0.16 m reel-seat + grip length).  The total swingweight is the sum of the
section contributions.

The linear-density assumption is only valid for a section balance point in
:math:`[l_{sec}/3,\ 2 l_{sec}/3]`; values outside this range flag an unreliable
estimate (the corrupted butt-section balance point of a finished rod is
exempt, since the blank balance point is inferred rather than used directly).

Units
------------------------------
The estimator works in SI units (kg, m) internally, so
:class:`~flycastsim.rod.swingweight.SwingweightResult` reports
:attr:`~flycastsim.rod.swingweight.SwingweightResult.swingweight` in
:math:`\mathrm{kg\,m^2}`.  The paper quotes :math:`\mathrm{g\,m^2}`; read
:attr:`~flycastsim.rod.swingweight.SwingweightResult.swingweight_gm2` for that.
The estimate is good to about :math:`\pm 1\ \mathrm{g\,m^2}` given careful
measurements (~0.1 g mass, ~1 mm length resolution).

Measure procedure
------------------------------
For each rod section, butt to tip, measure and record:

#. the **section length**,
#. the **section mass**, and
#. the **balance point** — the distance from the *thick (butt) end* of the
   section to where it balances on a hard edge.

Also measure the **total assembled rod length**, used to estimate the
per-ferrule overlap ``(Σ l_sec − l_assembled) / n_ferrules``.

Example
------------------------------
Estimating the swingweight of a finished four-piece rod:

.. code-block:: python

    from flycastsim import swingweight, RodSection

    sections = [
        RodSection.from_grams(68.9, 0.72, 0.16, name="butt"),
        RodSection.from_grams(15.9, 0.72, 0.31, name="section 2"),
        RodSection.from_grams(8.4, 0.72, 0.32, name="section 3"),
        RodSection.from_grams(3.7, 0.72, 0.33, name="tip"),
    ]

    result = swingweight(sections, assembled_length=2.73, has_reel_seat=True)

    print(f"Swingweight: {result.swingweight_gm2:.1f} g.m^2")  # ~63.5
    for s in result.sections:
        print(f"  {s.name:10s} d={s.d:.3f} m  I={s.I_sec_gm2:.2f} g.m^2")

    # ferrule overlap and reel-seat / grip split
    print(result.ferrule_overlap, result.reel_seat_grip)

Pass ``has_reel_seat=False`` for a bare blank (no reel-seat correction; the
butt section then uses its measured balance point directly).

The bundled worked-example rods from the paper are loadable for presets or
validation:

.. code-block:: python

    from flycastsim.rod import load_example_rods

    for rod in load_example_rods():
        res = swingweight(rod.sections, rod.assembled_length,
                          has_reel_seat=rod.has_reel_seat)
        print(rod.label, res.swingweight_gm2, "vs paper",
              rod.reference_swingweight_gm2)

A Plotly chart of each section's contribution (the paper's recommended
diagnostic) is available via
:func:`flycastsim.rod.plot_swingweight_contributions`.

Streamlit app
------------------------------
This powers the **Rod parameters** section of the Streamlit dashboard, where
the per-section measurements can be entered in an editable table (or loaded
from the example presets), the reel-seat correction toggled, and the resulting
swingweight, contribution chart and per-section breakdown displayed
interactively.

Validation
------------------------------
The implementation reproduces the worked examples tabulated in the paper to
within its stated tolerance (see ``tests/unit/test_rod_swingweight.py``):

* Dan Craft FT 905-4 blank — :math:`I_s \approx 56.1\ \mathrm{g\,m^2}`
* Sage Z-Axis 590-4 (finished rod) — :math:`I_s \approx 63.1\ \mathrm{g\,m^2}`

Sources
------------------------------
* G. Løvoll and M. Angus, *Measuring fly rod "swingweight"* (March 2008) —
  ``data/swingweight.pdf``, also at
  `sexyloops.com <https://www.sexyloops.com/articles/swingweight.pdf>`_.
