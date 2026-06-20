"""Fly-rod *swingweight* (butt-axis moment of inertia) estimation.

This module implements the method of Løvoll & Angus, *"Measuring fly rod
swingweight"* (March 2008, bundled as ``data/swingweight.pdf`` and available at
https://www.sexyloops.com/articles/swingweight.pdf).

**Swingweight** is defined there as the moment of inertia (MOI) of a single
handed multi-piece fly rod about an axis at the *butt* of the rod (``x = 0``),
i.e.

.. math::

    I_s = \\int_0^l \\mu(x)\\, x^2\\, dx,

where :math:`\\mu(x)` is the linear mass density at distance ``x`` from the
butt.  The mass distribution is unknown, so the paper makes two assumptions to
estimate it from simple non-destructive measurements:

1. The mass density of each section decreases **linearly** with distance from
   the thick (butt) end of that section.
2. The reel seat and grip are modelled as a thin uniform cylinder so the butt
   *blank* mass centre can be inferred from the section above it.

Per section, with mass ``m_sec``, length ``l_sec`` and balance point ``x_cm``
(distance from the thick end of the section to its mass centre), the MOI about
the rod-butt axis is (paper eq. 1):

.. math::

    I_{sec} = m_{sec} l_{sec}^2\\left(\\frac{x_{cm}}{l_{sec}} - \\frac16\\right)
              - m_{sec} x_{cm}^2 + m_{sec} d_{sec}^2,

where the first two terms are the MOI about the section's own mass centre
(:math:`I_{cm}`) and the last term is the parallel-axis shift to the rod butt
by ``d_sec`` (distance from the rod butt to the section's balance point).  The
``d_sec`` values are built up cumulatively while removing the **ferrule
overlap** (eqs. 2-5), and the butt section gets a dedicated **reel-seat / grip
correction** (eqs. 6-9).

The paper works in grams and metres, giving swingweight in :math:`g\\,m^2`.
Internally this module works in SI units (kg, m), so :attr:`SwingweightResult`
returns ``I_s`` in :math:`kg\\,m^2`; multiply by 1000 (or read
:attr:`SwingweightResult.swingweight_gm2`) for the paper's :math:`g\\,m^2`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Assumed length of the reel seat + grip, modelled as a uniform cylinder [m]
#: (paper, sec. 2, point 2).
L_RG_DEFAULT = 0.16


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
@dataclass
class RodSection:
    """A single rod section, numbered from butt (1) to tip.

    Args:
        mass: Section mass [kg].
        length: Section length [m].
        mass_center: Distance from the thick (butt) end of the *section* to its
            balance point / mass centre [m] (the paper's ``x_cm``).
        name: Optional human-readable label (e.g. ``"butt"``, ``"tip"``).
    """

    mass: float
    length: float
    mass_center: float
    name: str = ""

    @classmethod
    def from_grams(cls, mass_g: float, length: float, mass_center: float,
                   name: str = "") -> "RodSection":
        """Build a section from a mass given in **grams** (length/CoM in m)."""
        return cls(mass=mass_g / 1000.0, length=length,
                   mass_center=mass_center, name=name)


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
@dataclass
class SectionResult:
    """Per-section swingweight breakdown (all MOI in :math:`kg\\,m^2`)."""

    name: str
    mass: float
    length: float
    mass_center: float
    #: Distance from the rod butt to this section's balance point [m].
    d: float
    #: MOI about the section's own mass centre [kg m^2].
    I_cm: float
    #: MOI about the rod-butt axis [kg m^2].
    I_sec: float

    @property
    def I_sec_gm2(self) -> float:
        """Section MOI in :math:`g\\,m^2` (the paper's units)."""
        return self.I_sec * 1000.0


@dataclass
class ReelSeatGrip:
    """Reel-seat / grip correction applied to the butt section (eqs. 6-9)."""

    #: Inferred mass centre of the butt *blank* (eq. 6) [m].
    x_bcm: float
    #: Estimated reel-seat + grip mass (eq. 7) [kg].
    mass: float
    #: Estimated effective butt-blank mass (eq. 8) [kg].
    blank_mass: float
    #: Reel-seat + grip MOI about the butt axis (eq. 9) [kg m^2].
    I_rg: float
    #: Butt-blank MOI about the butt axis [kg m^2].
    I_blank: float
    #: Assumed reel-seat + grip length [m].
    length: float


@dataclass
class SwingweightResult:
    """Full swingweight estimate for a rod.

    Attributes:
        swingweight: Total MOI about the rod-butt axis [kg m^2].
        sections: Per-section breakdown.
        assembled_length: Measured length of the assembled rod [m].
        sum_section_length: Sum of the individual section lengths [m].
        ferrule_overlap: Estimated overlap per ferrule [m].
        n_ferrules: Number of ferrules (``n_sections - 1``).
        reel_seat_grip: Reel-seat / grip correction details, or ``None`` for a
            bare blank.
    """

    swingweight: float
    sections: list = field(default_factory=list)
    assembled_length: float = 0.0
    sum_section_length: float = 0.0
    ferrule_overlap: float = 0.0
    n_ferrules: int = 0
    reel_seat_grip: ReelSeatGrip | None = None

    @property
    def swingweight_gm2(self) -> float:
        """Total swingweight in :math:`g\\,m^2` (the paper's units)."""
        return self.swingweight * 1000.0


# ---------------------------------------------------------------------------
# Core formulas
# ---------------------------------------------------------------------------
def section_moi_about_cm(mass: float, length: float,
                         mass_center: float) -> float:
    """MOI of a section about its own mass centre (paper eq. 19/20).

    .. math::

        I_{cm} = m l^2\\left(\\frac{x_{cm}}{l} - \\frac16\\right) - m x_{cm}^2.

    Args:
        mass: Section mass [kg].
        length: Section length [m].
        mass_center: Balance point from the thick end of the section [m].

    Returns:
        MOI about the section mass centre [kg m^2].
    """
    return (mass * length ** 2 * (mass_center / length - 1.0 / 6.0)
            - mass * mass_center ** 2)


def section_moi(mass: float, length: float, mass_center: float,
                d: float) -> float:
    """MOI of a section about the rod-butt axis (paper eq. 1).

    The parallel-axis theorem shifts :func:`section_moi_about_cm` from the
    section mass centre to the rod butt using ``d`` (rod-butt-to-balance-point
    distance):

    .. math::

        I_{sec} = I_{cm} + m\\, d^2.

    Args:
        mass: Section mass [kg].
        length: Section length [m].
        mass_center: Balance point from the thick end of the section [m].
        d: Distance from the rod butt to the section's balance point [m].

    Returns:
        MOI about the rod-butt axis [kg m^2].
    """
    return section_moi_about_cm(mass, length, mass_center) + mass * d ** 2


def reel_seat_grip_correction(butt: RodSection, second: RodSection,
                              l_rg: float = L_RG_DEFAULT) -> ReelSeatGrip:
    """Correct the butt-section MOI for the reel seat and grip (eqs. 6-9).

    On a finished rod the reel seat and grip add mass at the very butt, which
    corrupts the *measured* butt-section balance point.  Following the paper we

    1. infer the butt *blank* mass centre from the section above it (eq. 6)::

           x_bcm = l_1 * (x_cm2 / l_2)

    2. model the reel seat + grip as a uniform cylinder of length ``l_rg`` with
       its mass centre at ``l_rg / 2`` and back out its mass (eq. 7) and the
       effective butt-blank mass (eq. 8);
    3. add the cylinder MOI (eq. 9) to the blank MOI to get the corrected butt
       MOI.

    Args:
        butt: The butt section (section 1), with *measured* mass and CoM.
        second: The section directly above the butt (section 2).
        l_rg: Assumed reel-seat + grip length [m].

    Returns:
        A :class:`ReelSeatGrip` with the inferred quantities; ``I_rg`` +
        ``I_blank`` is the corrected butt-section MOI about the butt axis.

    Raises:
        ValueError: If the geometry is degenerate (e.g. the inferred blank CoM
            coincides with the reel-seat/grip CoM, making eq. 7 singular).
    """
    x_bcm = butt.length * (second.mass_center / second.length)
    x_rgcm = l_rg / 2.0
    denom = x_rgcm - x_bcm
    if denom == 0:
        raise ValueError(
            "Degenerate reel-seat/grip geometry: inferred blank mass centre "
            "coincides with the reel-seat/grip mass centre (eq. 7 singular).")
    m_rg = butt.mass * (butt.mass_center - x_bcm) / denom
    m_blank = butt.mass - m_rg
    I_rg = (1.0 / 3.0) * m_rg * l_rg ** 2
    # The blank sits at the rod butt, so the parallel-axis distance to its
    # mass centre is x_bcm; section_moi then returns the MOI about the rod-butt
    # axis (eq. 19), m_blank * l^2 * (x_bcm/l - 1/6).
    I_blank = section_moi(m_blank, butt.length, x_bcm, x_bcm)
    return ReelSeatGrip(x_bcm=x_bcm, mass=m_rg, blank_mass=m_blank,
                        I_rg=I_rg, I_blank=I_blank, length=l_rg)


# ---------------------------------------------------------------------------
# Top-level estimator
# ---------------------------------------------------------------------------
def swingweight(sections, assembled_length: float, *,
                has_reel_seat: bool = True,
                l_rg: float = L_RG_DEFAULT) -> SwingweightResult:
    """Estimate the swingweight of a multi-piece fly rod.

    Implements the full Løvoll & Angus procedure: per-section MOI about the
    rod-butt axis (eq. 1) with cumulative ferrule-overlap removal (eqs. 2-5)
    and a reel-seat / grip correction for the butt section (eqs. 6-9).

    Args:
        sections: Rod sections ordered **butt to tip** (list of
            :class:`RodSection`).  At least one section is required; the
            reel-seat correction needs at least two.
        assembled_length: Measured length of the fully assembled rod [m].  Used
            to estimate the per-ferrule overlap
            ``(Σ l_sec - assembled_length) / n_ferrules``.
        has_reel_seat: If ``True`` (a finished rod) apply the reel-seat / grip
            correction to the butt section.  If ``False`` (a bare blank) the
            butt section uses its measured balance point directly.
        l_rg: Assumed reel-seat + grip length [m] (paper default 0.16 m).

    Returns:
        A :class:`SwingweightResult` with the total swingweight and a
        per-section breakdown.

    Raises:
        ValueError: If ``sections`` is empty, or a reel-seat correction is
            requested for a single-section rod.
    """
    sections = list(sections)
    n = len(sections)
    if n == 0:
        raise ValueError("At least one rod section is required.")

    sum_len = sum(s.length for s in sections)
    n_ferrules = n - 1
    delta_total = sum_len - assembled_length
    overlap = delta_total / n_ferrules if n_ferrules > 0 else 0.0

    cumulative_length = 0.0  # sum of section lengths below the current one
    section_results = []
    rsg = None
    total = 0.0

    for i, sec in enumerate(sections):
        name = sec.name or (
            "butt" if i == 0 else "tip" if i == n - 1 else f"section {i + 1}")
        if i == 0:
            # Butt section: balance point measured from the rod butt directly,
            # so d == its own balance point.  Distance subtracted for overlap
            # is zero (no ferrule below the butt).
            d = sec.mass_center
            if has_reel_seat:
                if n < 2:
                    raise ValueError(
                        "Reel-seat / grip correction needs at least two "
                        "sections (the butt blank CoM is inferred from the "
                        "section above). Pass has_reel_seat=False for a "
                        "single-section blank.")
                rsg = reel_seat_grip_correction(sec, sections[1], l_rg=l_rg)
                # For the corrected butt the "I_cm" concept is not meaningful;
                # report the blank's own-centre MOI for the breakdown.
                I_cm = section_moi_about_cm(rsg.blank_mass, sec.length,
                                            rsg.x_bcm)
                I_sec = rsg.I_blank + rsg.I_rg
                d = rsg.x_bcm
            else:
                I_cm = section_moi_about_cm(sec.mass, sec.length,
                                            sec.mass_center)
                I_sec = section_moi(sec.mass, sec.length, sec.mass_center, d)
        else:
            # d_k = (Σ lengths below) + x_cm_k - k_below * overlap, where
            # k_below = i ferrules sit below section (i+1).
            d = cumulative_length + sec.mass_center - i * overlap
            I_cm = section_moi_about_cm(sec.mass, sec.length, sec.mass_center)
            I_sec = section_moi(sec.mass, sec.length, sec.mass_center, d)

        section_results.append(SectionResult(
            name=name, mass=sec.mass, length=sec.length,
            mass_center=sec.mass_center, d=d, I_cm=I_cm, I_sec=I_sec))
        total += I_sec
        cumulative_length += sec.length

    return SwingweightResult(
        swingweight=total, sections=section_results,
        assembled_length=assembled_length, sum_section_length=sum_len,
        ferrule_overlap=overlap, n_ferrules=n_ferrules,
        reel_seat_grip=rsg)
