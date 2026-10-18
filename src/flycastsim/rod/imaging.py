"""Rod centre-line extraction from static bend-test images.

The bend tests photograph a clamped rod against a plain wall.  This module
turns each frame into sub-pixel centre-line points (and a tip position) for
the profile fit in :mod:`flycastsim.rod.profile_fit` (see
``docs/rod_profile.rst``).  Two kinds of frames are supported through the same
path:

* **raw** frames -- a dark rod on a light, unevenly lit wall, optionally with
  a background frame (the scene without the rod) to subtract;
* **background-subtracted** frames -- a bright rod on a dark background, as
  produced by the existing image-processing pipeline (possibly with tracking
  annotations drawn on them).

Steps:

#. :func:`ridge_image` -- optional background subtraction, polarity
   normalisation (rod bright) and a morphological white top-hat, which keeps
   features narrower than ``tophat_size`` (the rod) and removes uneven
   lighting and large objects;
#. :func:`trace_centerline` -- ridge following from a start point near the
   clamp: at each step a short intensity profile across the rod gives a
   sub-pixel centre (intensity-weighted centroid around the peak), then the
   trace advances along the local tangent until the rod contrast fades at the
   tip, where the tip is located to sub-pixel accuracy along the tangent (at
   half the local rod contrast);
#. :func:`reject_outliers` -- drops points that deviate from a running
   median of their neighbours (guides, wraps, ferrules, drawn labels).

Coordinates are image pixels ``(x, y)`` with ``x`` to the right and ``y``
**down**.  Converting to metres relative to the clamp is part of the fit.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import ndimage


def load_gray(path: str | Path) -> np.ndarray:
    """Load an image as a float grey-scale array (0..255)."""
    from PIL import Image

    with Image.open(path) as im:
        return np.asarray(im.convert("L"), dtype=float)


def ridge_image(image: np.ndarray, background: np.ndarray | None = None, *,
                polarity: str = "auto", tophat_size: int = 31,
                smooth_sigma: float = 1.0) -> np.ndarray:
    """Normalise a frame so the rod is a bright ridge on a zero background.

    Args:
        image: Grey-scale frame.
        background: Optional frame of the same scene without the rod.  The
            absolute difference ``|image - background|`` is used, so both
            the dark blank and its specular highlight count as rod and the
            centre is not biased towards either side; the polarity is then
            ``"bright"``.
        polarity: ``"bright"`` (rod brighter than its surroundings),
            ``"dark"`` (rod darker, e.g. raw frames) or ``"auto"``.  Without
            a background, a raw frame's highlight is lost and the centre may
            be biased by a pixel or two towards the dark side.
        tophat_size: Size [px] of the top-hat structuring element; must be
            clearly wider than the rod.
        smooth_sigma: Gaussian pre-smoothing [px] to suppress pixel noise
            (0 disables it).

    Returns:
        Non-negative ridge-strength image.
    """
    img = np.asarray(image, dtype=float)
    if background is not None:
        img = np.abs(img - np.asarray(background, dtype=float))
        if polarity == "auto":
            polarity = "bright"
    if smooth_sigma > 0:
        img = ndimage.gaussian_filter(img, smooth_sigma)
    if polarity == "auto":
        bright = ndimage.white_tophat(img, size=tophat_size)
        dark = ndimage.black_tophat(img, size=tophat_size)
        # The rod is a thin line, so it dominates the extreme tail of the
        # matching top-hat response.
        polarity = ("bright" if np.percentile(bright, 99.9)
                    >= np.percentile(dark, 99.9) else "dark")
        return bright if polarity == "bright" else dark
    if polarity == "bright":
        return ndimage.white_tophat(img, size=tophat_size)
    if polarity == "dark":
        return ndimage.black_tophat(img, size=tophat_size)
    raise ValueError("polarity must be 'auto', 'bright' or 'dark'")


@dataclass
class CenterlineTrace:
    """Result of :func:`trace_centerline`.

    Attributes:
        points: Centre-line points ``(N, 2)`` from the start towards the tip
            [px].
        strength: Ridge strength (profile peak) at each point.
        tip: Sub-pixel tip position ``(2,)`` [px].
        stop_reason: Why the trace stopped (``"faded"``, ``"edge"`` or
            ``"max_steps"``), or ``"kink"`` if it was cut at a sharp kink
            where something attached to the tip (hook line, drawn label)
            continues beyond the rod.
    """

    points: np.ndarray
    strength: np.ndarray
    tip: np.ndarray
    stop_reason: str

    @property
    def arc_length(self) -> float:
        """Polyline length from the first point to the tip [px]."""
        pts = np.vstack([self.points, self.tip])
        return float(np.hypot(*np.diff(pts, axis=0).T).sum())


def _profile_centre(ridge, centre, normal, half_width, peak_half_width,
                    min_peak=None):
    """Sub-pixel ridge centre on a profile across the rod.

    Without ``min_peak`` the profile maximum is used.  With ``min_peak`` the
    local maximum above ``min_peak`` *closest to the predicted centre* is
    used, so bright objects beside the rod (labels, markers) are not
    followed.

    Returns ``(offset, peak)``: the intensity-weighted centroid offset along
    ``normal`` within ``peak_half_width`` of the chosen maximum, and that
    maximum above the profile baseline (0 if none qualifies).
    """
    offsets = np.arange(-half_width, half_width + 1, dtype=float)
    xs = centre[0] + offsets * normal[0]
    ys = centre[1] + offsets * normal[1]
    prof = ndimage.map_coordinates(ridge, [ys, xs], order=1, mode="constant")
    prof = prof - np.median(prof)
    if min_peak is None:
        i = int(np.argmax(prof))
    else:
        interior = prof[1:-1]
        is_max = ((interior >= prof[:-2]) & (interior >= prof[2:])
                  & (interior > min_peak))
        cand = np.nonzero(is_max)[0] + 1
        if len(cand) == 0:
            return 0.0, 0.0
        i = int(cand[np.argmin(np.abs(offsets[cand]))])
    peak = prof[i]
    lo, hi = max(i - peak_half_width, 0), min(i + peak_half_width + 1,
                                               len(prof))
    w = np.clip(prof[lo:hi], 0.0, None)
    if peak <= 0 or w.sum() == 0:
        return 0.0, 0.0
    return float((w * offsets[lo:hi]).sum() / w.sum()), float(peak)


def trace_centerline(ridge: np.ndarray, start: tuple[float, float],
                     direction: tuple[float, float], *, step: float = 4.0,
                     half_width: int = 12, peak_half_width: int = 4,
                     stop_fraction: float = 0.25, n_reference: int = 20,
                     patience: int = 3, turn_smoothing: float = 0.5,
                     max_lateral: float | None = None,
                     kink_window: float = 24.0, kink_angle: float = 15.0,
                     max_steps: int = 10000) -> CenterlineTrace:
    """Follow the rod ridge from ``start`` towards the tip.

    Args:
        ridge: Ridge-strength image from :func:`ridge_image`.
        start: Point on (or within ``half_width`` of) the rod near the clamp,
            ``(x, y)`` [px].  Start a little outboard of the clamp hardware.
        direction: Approximate initial direction towards the tip.
        step: Step length along the rod [px].
        half_width: Half length of the cross profile [px]; it must cover the
            lateral motion of the rod between steps but stay clear of
            neighbouring objects.
        peak_half_width: Half width of the centroid window around the
            profile maximum [px] (about the rod's half width plus blur).
        stop_fraction: The trace stops when the ridge peak falls below this
            fraction of the local reference strength...
        n_reference: ...the median peak of the last ``n_reference``
            accepted points (so a rod that thins towards the tip is
            followed)...
        patience: ...for this many consecutive steps.
        turn_smoothing: Weight of the new direction when updating the
            tangent (1 = no smoothing).
        max_lateral: Largest sideways correction per step [px] (default
            ``step``); larger jumps are treated as a gap in the rod.  Each
            profile follows the ridge peak closest to the predicted position
            among peaks above half the local strength.
        kink_window: Chord length [px] before and after each point used to
            detect a kink at the tip...
        kink_angle: ...and the turn [deg] that counts as one.  Only the last
            third of the trace is searched; the rod itself bends smoothly.
        max_steps: Safety limit on the number of steps.

    Returns:
        The :class:`CenterlineTrace`.
    """
    ridge = np.asarray(ridge, dtype=float)
    h, w = ridge.shape
    t = np.asarray(direction, dtype=float)
    t /= np.hypot(*t)
    n = np.array([-t[1], t[0]])
    # Snap the start point onto the ridge.
    off, peak = _profile_centre(ridge, np.asarray(start, float), n,
                                half_width, peak_half_width)
    if peak <= 0:
        raise ValueError("no rod ridge found at the start point")
    p = np.asarray(start, float) + off * n
    points, strengths = [p], [peak]
    max_lateral = step if max_lateral is None else max_lateral
    weak = 0
    reason = "max_steps"
    for _ in range(max_steps):
        q = p + step * t
        if not (half_width <= q[0] < w - half_width
                and half_width <= q[1] < h - half_width):
            reason = "edge"
            break
        n = np.array([-t[1], t[0]])
        reference = float(np.median(strengths[-n_reference:]))
        off, peak = _profile_centre(ridge, q, n, half_width, peak_half_width,
                                    min_peak=stop_fraction * reference)
        if peak < stop_fraction * reference or abs(off) > max_lateral:
            weak += 1
            if weak >= patience:
                reason = "faded"
                break
            p = q                    # coast straight on through a weak gap
            continue
        weak = 0
        c = q + off * n
        t_new = (c - p) / np.hypot(*(c - p))
        t = turn_smoothing * t_new + (1 - turn_smoothing) * t
        t /= np.hypot(*t)
        p = c
        points.append(c)
        strengths.append(peak)

    pts = np.array(points)
    strength = np.array(strengths)
    # Look for the kink on outlier-free points, so local bumps (guides,
    # drawn marker dots) do not count.
    good = np.nonzero(reject_outliers(pts))[0]
    k = _end_kink(pts[good], kink_window, kink_angle)
    if k is not None:
        k = good[k]
        return CenterlineTrace(points=pts[:k + 1], strength=strength[:k + 1],
                               tip=pts[k].copy(), stop_reason="kink")
    # Half the local rod contrast marks the end of a blurred rod.
    level = 0.5 * float(np.median(strength[-5:]))
    tip = _locate_tip(ridge, pts, level, step, half_width, peak_half_width)
    return CenterlineTrace(points=pts, strength=strength, tip=tip,
                           stop_reason=reason)


def _end_kink(pts, window, angle_deg):
    """Index of the first sharp kink in the last third of ``pts``."""
    if len(pts) < 10:
        return None
    seg = np.hypot(*np.diff(pts, axis=0).T)
    arc = np.concatenate([[0.0], np.cumsum(seg)])
    cos_max = np.cos(np.radians(angle_deg))
    for i in range(int(2 * len(pts) / 3), len(pts)):
        j0 = np.searchsorted(arc, arc[i] - window)
        j1 = np.searchsorted(arc, arc[i] + window)
        if j0 >= i or j1 >= len(pts) or arc[i] - arc[j0] < 0.75 * window:
            continue
        a, b = pts[i] - pts[j0], pts[j1] - pts[i]
        if a @ b < cos_max * np.hypot(*a) * np.hypot(*b):
            return i
    return None


def _locate_tip(ridge, pts, level, step, half_width, peak_half_width):
    """Sub-pixel tip: where the ridge peak drops through ``level`` beyond
    the last traced point, scanning along the end tangent."""
    end = pts[-1]
    if len(pts) >= 3:
        t = pts[-1] - pts[-3]
    elif len(pts) == 2:
        t = pts[-1] - pts[-2]
    else:
        return end
    t = t / np.hypot(*t)
    n = np.array([-t[1], t[0]])
    dist = np.arange(0.0, 3 * step + 0.25, 0.25)
    peaks = np.array([_profile_centre(ridge, end + d * t, n, half_width,
                                      peak_half_width)[1] for d in dist])
    below = np.nonzero(peaks < level)[0]
    if len(below) == 0 or below[0] == 0:
        return end + (dist[-1] if len(below) == 0 else 0.0) * t
    i = below[0]
    # linear interpolation of the crossing between samples i-1 and i
    f = (peaks[i - 1] - level) / (peaks[i - 1] - peaks[i])
    return end + (dist[i - 1] + f * (dist[i] - dist[i - 1])) * t


def reject_outliers(points: np.ndarray, window: int = 7,
                    threshold: float = 4.0, min_mad: float = 0.25
                    ) -> np.ndarray:
    """Boolean mask of points consistent with their neighbours.

    Each point is compared with the running median (``window`` points) of
    its neighbours, measured perpendicular to the local direction; points
    deviating by more than ``threshold`` robust standard deviations (MAD,
    at least ``min_mad`` px) are rejected.
    """
    pts = np.asarray(points, dtype=float)
    if len(pts) < window:
        return np.ones(len(pts), dtype=bool)
    med = np.column_stack([ndimage.median_filter(pts[:, k], size=window,
                                                 mode="nearest")
                           for k in range(2)])
    tangent = np.gradient(med, axis=0)
    tangent /= np.maximum(np.hypot(*tangent.T), 1e-12)[:, None]
    dev = (pts - med)
    normal_dev = np.abs(-dev[:, 0] * tangent[:, 1] + dev[:, 1] * tangent[:, 0])
    mad = max(1.4826 * np.median(normal_dev), min_mad)
    return normal_dev <= threshold * mad


def extract_centerline(image: np.ndarray, start: tuple[float, float],
                       direction: tuple[float, float],
                       background: np.ndarray | None = None, *,
                       polarity: str = "auto", tophat_size: int = 31,
                       **trace_kwargs) -> CenterlineTrace:
    """Ridge image, trace and outlier rejection in one call.

    The returned trace holds only the accepted points.  Keyword arguments
    beyond those of :func:`ridge_image` go to :func:`trace_centerline`.
    """
    ridge = ridge_image(image, background, polarity=polarity,
                        tophat_size=tophat_size)
    trace = trace_centerline(ridge, start, direction, **trace_kwargs)
    keep = reject_outliers(trace.points)
    return CenterlineTrace(points=trace.points[keep],
                           strength=trace.strength[keep], tip=trace.tip,
                           stop_reason=trace.stop_reason)
