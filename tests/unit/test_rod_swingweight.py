# -*- coding: utf-8 -*-
"""Unit tests for fly-rod swingweight estimation.

Validates the implementation of Løvoll & Angus, *"Measuring fly rod
swingweight"* (2008), against the worked examples tabulated in the paper and
checks the individual building blocks (per-section MOI and the reel-seat/grip
correction).
"""
import math

import pytest

from flycastsim import swingweight, RodSection
from flycastsim.rod import (load_example_rods, section_moi,
                            section_moi_about_cm, reel_seat_grip_correction,
                            L_RG_DEFAULT)


# The paper quotes an uncertainty of order +-1 g.m^2 on the estimate.
PAPER_TOL_GM2 = 1.0


def test_example_rods_match_paper_totals():
    """Total swingweight matches the paper's tabulated values (+-1 g.m^2)."""
    rods = load_example_rods()
    assert len(rods) >= 2
    for rod in rods:
        res = swingweight(rod.sections, rod.assembled_length,
                          has_reel_seat=rod.has_reel_seat)
        assert abs(res.swingweight_gm2
                   - rod.reference_swingweight_gm2) <= PAPER_TOL_GM2, rod.label


def test_dan_craft_blank_per_section():
    """Per-section MOI for the Dan Craft FT 905-4 blank (paper page 5)."""
    rod = next(r for r in load_example_rods() if r.make == "Dan Craft")
    res = swingweight(rod.sections, rod.assembled_length,
                      has_reel_seat=False)
    expected = [3.11, 17.51, 19.89, 15.58]
    got = [s.I_sec_gm2 for s in res.sections]
    assert got == pytest.approx(expected, abs=0.05)
    assert res.swingweight_gm2 == pytest.approx(56.1, abs=PAPER_TOL_GM2)


def test_section_moi_parallel_axis():
    """``section_moi`` == ``I_cm`` + m d^2 (parallel-axis theorem)."""
    m, l, x_cm, d = 0.0172, 0.72, 0.315, 0.988
    I_cm = section_moi_about_cm(m, l, x_cm)
    assert section_moi(m, l, x_cm, d) == pytest.approx(I_cm + m * d ** 2)
    # When the axis passes through the balance point (d == 0), only I_cm
    # remains.
    assert section_moi(m, l, x_cm, 0.0) == pytest.approx(I_cm)


def test_section_moi_about_cm_formula():
    """Closed-form check of eq. 19/20 against a hand calculation."""
    m, l, x_cm = 0.0234, 0.715, 0.305
    expected = m * l ** 2 * (x_cm / l - 1.0 / 6.0) - m * x_cm ** 2
    assert section_moi_about_cm(m, l, x_cm) == pytest.approx(expected)


def test_reel_seat_grip_mass_split():
    """Reel-seat/grip mass split (eqs. 6-8) for the Sage Z-Axis butt."""
    butt = RodSection.from_grams(68.9, 0.72, 0.16)
    second = RodSection.from_grams(15.9, 0.72, 0.31)
    rsg = reel_seat_grip_correction(butt, second)

    x_bcm = butt.length * (second.mass_center / second.length)
    x_rgcm = L_RG_DEFAULT / 2.0
    m_rg = butt.mass * (butt.mass_center - x_bcm) / (x_rgcm - x_bcm)

    assert rsg.x_bcm == pytest.approx(x_bcm)
    assert rsg.mass == pytest.approx(m_rg)
    assert rsg.blank_mass == pytest.approx(butt.mass - m_rg)
    # Mass is conserved: blank + reel/grip == measured butt mass.
    assert rsg.blank_mass + rsg.mass == pytest.approx(butt.mass)
    # Uniform-cylinder MOI (eq. 9).
    assert rsg.I_rg == pytest.approx(m_rg * L_RG_DEFAULT ** 2 / 3.0)


def test_reel_seat_increases_butt_moi():
    """Applying the reel-seat correction changes the butt-section MOI."""
    rod = next(r for r in load_example_rods() if r.make == "Sage")
    with_seat = swingweight(rod.sections, rod.assembled_length,
                            has_reel_seat=True)
    without = swingweight(rod.sections, rod.assembled_length,
                          has_reel_seat=False)
    # The non-butt sections are unaffected by the correction.
    for a, b in zip(with_seat.sections[1:], without.sections[1:]):
        assert a.I_sec == pytest.approx(b.I_sec)
    # The butt section differs once the heavy reel seat is accounted for.
    assert with_seat.sections[0].I_sec != pytest.approx(without.sections[0].I_sec)


def test_ferrule_overlap_estimate():
    """Per-ferrule overlap = (sum section lengths - assembled) / n_ferrules."""
    rod = next(r for r in load_example_rods() if r.make == "Sage")
    res = swingweight(rod.sections, rod.assembled_length,
                      has_reel_seat=rod.has_reel_seat)
    sum_len = sum(s.length for s in rod.sections)
    n_ferrules = len(rod.sections) - 1
    expected = (sum_len - rod.assembled_length) / n_ferrules
    assert res.n_ferrules == n_ferrules
    assert res.ferrule_overlap == pytest.approx(expected)


def test_single_section_blank():
    """A single-section blank has no ferrules and uses its measured CoM."""
    sec = RodSection.from_grams(20.0, 1.0, 0.4)
    res = swingweight([sec], assembled_length=1.0, has_reel_seat=False)
    assert res.n_ferrules == 0
    assert res.ferrule_overlap == 0.0
    # d == measured balance point for the lone butt section.
    assert res.sections[0].d == pytest.approx(0.4)
    assert res.swingweight == pytest.approx(
        section_moi(0.02, 1.0, 0.4, 0.4))


def test_single_section_reel_seat_raises():
    """The reel-seat correction needs the section above the butt."""
    sec = RodSection.from_grams(20.0, 1.0, 0.4)
    with pytest.raises(ValueError):
        swingweight([sec], assembled_length=1.0, has_reel_seat=True)


def test_empty_sections_raises():
    with pytest.raises(ValueError):
        swingweight([], assembled_length=1.0)


def test_swingweight_units_consistency():
    """``swingweight_gm2`` is exactly 1000x the SI value."""
    rod = load_example_rods()[0]
    res = swingweight(rod.sections, rod.assembled_length,
                      has_reel_seat=rod.has_reel_seat)
    assert res.swingweight_gm2 == pytest.approx(res.swingweight * 1000.0)
    assert math.isfinite(res.swingweight)
