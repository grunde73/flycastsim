# -*- coding: utf-8 -*-
"""Tests for rod centre-line extraction (:mod:`flycastsim.rod.imaging`).

Synthetic frames are rendered from an elastica rod shape with a tapering,
Gaussian cross-section and a blurred tip (so half the local contrast marks
the true tip), in the two styles the bend tests produce:

* background-subtracted: bright rod on black, with noise, guide ticks and
  drawn label blobs next to the rod;
* raw: dark rod on an unevenly lit wall, with and without a background
  frame.

The traced points must lie on the true centre line to sub-pixel accuracy and
the tip must be found to about a pixel.  If the PA905 bend frames are present
in ``assets/``, the trace is also checked against the hand-tracked markers.
"""
from pathlib import Path

import numpy as np
import pytest
from scipy.spatial import cKDTree
from scipy.special import erfc

from flycastsim.rod import solve_cantilever_fd
from flycastsim.rod.imaging import (extract_centerline, load_gray,
                                    reject_outliers, ridge_image,
                                    trace_centerline)

SHAPE = (520, 720)                      # rows, cols
CLAMP_PX = np.array([680.0, 60.0])      # (x, y), rod points left
SCALE = 250.0                           # px per metre


def _true_curve(tip_load=0.6):
    EI = lambda s: 3 + 22 * np.exp(-1.8 * (s - 0.25))     # noqa: E731
    sol = solve_cantilever_fd(EI, 0.03, length=2.743, s_clamp=0.25,
                              tip_load=tip_load)
    s = np.linspace(sol.s_clamp, sol.length, 20000)
    x, y = sol.at(s)[:2]
    # rod points left; image y is down
    return np.column_stack([CLAMP_PX[0] - SCALE * x, CLAMP_PX[1] - SCALE * y])


def _render_rod(curve, sigma_butt=2.5, sigma_tip=1.0, end_blur=1.0):
    """Rod intensity in [0, 1] with a Gaussian cross-section of tapering
    width and a tip edge blurred with ``end_blur`` [px]."""
    rows, cols = np.mgrid[0:SHAPE[0], 0:SHAPE[1]]
    pix = np.column_stack([cols.ravel(), rows.ravel()]).astype(float)
    d, j = cKDTree(curve).query(pix, distance_upper_bound=15.0)
    inside = np.isfinite(d)
    sigma = np.interp(j[inside], [0, len(curve) - 1], [sigma_butt, sigma_tip])
    end, t_end = curve[-1], curve[-1] - curve[-50]
    t_end /= np.hypot(*t_end)
    p = pix[inside] - end
    along = p @ t_end
    perp = np.abs(p[:, 0] * t_end[1] - p[:, 1] * t_end[0])
    near_end = j[inside] > len(curve) - 200
    dist = np.where(near_end, perp, d[inside])
    val = np.exp(-dist**2 / (2 * sigma**2))
    val *= np.where(near_end, 0.5 * erfc(along / (np.sqrt(2) * end_blur)), 1)
    out = np.zeros(pix.shape[0])
    out[inside] = val
    return out.reshape(SHAPE)


def _decorations(curve, rng):
    """Guide ticks across the rod and label blobs beside it."""
    img = np.zeros(SHAPE)
    tangent = np.gradient(curve, axis=0)
    tangent /= np.hypot(*tangent.T)[:, None]
    for k in np.linspace(1500, 18000, 8).astype(int):
        c, t = curve[k], tangent[k]
        n = np.array([-t[1], t[0]])
        for o in np.linspace(-5, 5, 21):           # guide foot: short tick
            x, y = np.round(c + o * n).astype(int)
            img[y, x] = max(img[y, x], 0.6)
        x, y = np.round(c + 18 * n).astype(int)    # label blob
        img[y - 5:y + 5, x - 3:x + 4] = 1.5
    return img


def _start(curve):
    k = 400
    t = curve[k + 10] - curve[k]
    return curve[k], t / np.hypot(*t)


def _check(trace, curve, rms_px=0.3, max_px=1.0, tip_px=1.5):
    d, _ = cKDTree(curve).query(trace.points)
    assert np.sqrt(np.mean(d**2)) < rms_px
    assert d.max() < max_px
    assert np.hypot(*(trace.tip - curve[-1])) < tip_px
    assert trace.stop_reason == "faded"


@pytest.fixture(scope="module")
def scene():
    curve = _true_curve()
    return curve, _render_rod(curve)


def test_background_subtracted_frame(scene):
    curve, rod = scene
    rng = np.random.default_rng(1)
    img = 120 * rod + 120 * _decorations(curve, rng) + rng.normal(0, 3, SHAPE)
    start, direction = _start(curve)
    _check(extract_centerline(img, start, direction), curve)


def _wall(rng):
    rows, cols = np.mgrid[0:SHAPE[0], 0:SHAPE[1]]
    wall = 200 - 0.06 * cols - 0.04 * rows
    wall[300:, 600:] -= 70                      # cabinet: large dark block
    return wall


@pytest.mark.parametrize("use_background", [True, False])
def test_raw_frame(scene, use_background):
    curve, rod = scene
    rng = np.random.default_rng(2)
    wall = _wall(rng)
    img = wall - 90 * rod + rng.normal(0, 3, SHAPE)
    background = wall + rng.normal(0, 3, SHAPE) if use_background else None
    start, direction = _start(curve)
    trace = extract_centerline(img, start, direction, background)
    _check(trace, curve)


def test_auto_polarity(scene):
    _, rod = scene
    rng = np.random.default_rng(3)
    dark = ridge_image(200 - 90 * rod + rng.normal(0, 2, SHAPE))
    bright = ridge_image(20 + 90 * rod + rng.normal(0, 2, SHAPE))
    on_rod = rod > 0.9
    for r in (dark, bright):
        assert r[on_rod].mean() > 10 * np.median(r)


def test_trace_arc_length(scene):
    curve, rod = scene
    start, direction = _start(curve)
    trace = trace_centerline(ridge_image(100 * rod), start, direction)
    true_len = np.hypot(*np.diff(curve[400:], axis=0).T).sum()
    assert trace.arc_length == pytest.approx(true_len, rel=0.005)


def test_reject_outliers_flags_spikes():
    s = np.linspace(0, 200, 60)
    pts = np.column_stack([s, 0.002 * s**2])
    pts[[10, 30, 31]] += [0, 6.0]
    keep = reject_outliers(pts)
    assert not keep[[10, 30, 31]].any()
    assert keep.sum() >= 54


# ---------------------------------------------------------------------------
# Real data (skipped when the assets are not available)
# ---------------------------------------------------------------------------
ASSETS = Path(__file__).resolve().parents[2] / "assets" / "PA905"
TRACK = ASSETS / "bend_vs_mass" / "paradigm_bend_track.txt"


def _tracked_markers(frame):
    rows = [line.split() for line in TRACK.read_text(errors="ignore")
            .splitlines()[1:] if line.strip()]
    data = np.array([[float(v) for v in r[1:5]] for r in rows])
    sel = data[:, 1] == frame + 1                 # slices are 1-based
    return data[sel][np.argsort(data[sel, 0])][:, 2:4]   # marker 1..9 (x, y)


needs_assets = pytest.mark.skipif(not TRACK.exists(),
                                  reason="PA905 bend assets missing")
#: Offset of the processed (cropped) frames in the raw frames, rod.yaml.
CROP_OFFSET = np.array([50.0, 913.0])


def _check_markers(trace, markers, check_tip=True):
    d, _ = cKDTree(trace.points).query(markers[1:-1])
    assert np.median(d) < 3.0                      # hand tracking ~ +-3 px
    if check_tip:
        assert np.hypot(*(trace.tip - markers[0])) < 10.0


@needs_assets
@pytest.mark.parametrize("frame", [0, 20, 37])
def test_pa905_annotated_frames_match_markers(frame):
    """Background-subtracted frames with tracking annotations drawn on.

    In frame 0 the foot of the drawn label "1" lies in line with the rod just
    past the tip, so only the centre line is checked there."""
    img = load_gray(ASSETS / "bend_vs_mass" / f"image_{frame:04d}.jpg")
    markers = _tracked_markers(frame)
    start = markers[-1] + np.array([-40.0, 0.0])  # just outboard of marker 9
    trace = extract_centerline(img, start, (-1.0, 0.0))
    _check_markers(trace, markers, check_tip=frame != 0)


@needs_assets
@pytest.mark.parametrize("frame", [0, 25])
def test_pa905_raw_frames_match_markers(frame):
    """Raw frames (dark rod on the wall) with the background frame."""
    raw_dir = ASSETS / "bend_vs_mass" / "raw_examples"
    img = load_gray(raw_dir / f"image_{frame:04d}.jpg")
    background = load_gray(raw_dir / "background.jpg")
    markers = _tracked_markers(frame) + CROP_OFFSET
    start = markers[-1] + np.array([-40.0, 0.0])
    trace = extract_centerline(img, start, (-1.0, 0.0), background)
    _check_markers(trace, markers)
