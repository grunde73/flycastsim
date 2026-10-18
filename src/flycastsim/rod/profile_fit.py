"""Fit a rod's stiffness :math:`EI(s)` and mass :math:`\\mu(s)` profiles.

Implements the parametrisations and the joint least-squares fit described in
``docs/rod_profile.rst``:

* :class:`SectionMassModel` -- linear mass density within each section, with
  jumps at the ferrules (the swingweight assumption of Løvoll & Angus 2008),
  parametrised by each section's mass and balance point so the measured
  values enter directly as priors.  An optional reel seat + grip is modelled
  as in :func:`~flycastsim.rod.swingweight.reel_seat_grip_correction`.
* :class:`MonotoneLogEI` -- a cubic B-spline in :math:`\\log EI` over the free
  length, constrained non-increasing from butt to tip, held constant behind
  the clamp.
* :func:`fit_profile` -- joint fit of static bend frames
  (:mod:`~flycastsim.rod.elastica`), tip-mass frequencies
  (:mod:`~flycastsim.rod.vibration`), a CCS point, section-mass priors and a
  smoothness penalty, with an optionally unknown load step per frame.

Observed bend shapes are given in physical coordinates relative to the clamp
(metres, ``y`` up).  Mapping image pixels to these coordinates (scale, clamp
position, camera roll) is a separate step.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
from scipy.interpolate import BSpline
from scipy.optimize import least_squares

from .elastica import (GRAVITY, ElasticaError, ElasticaSolution,
                       solve_cantilever_fd)
from .swingweight import L_RG_DEFAULT, RodSection, reel_seat_grip_correction
from .vibration import frequency_vs_tip_mass


# ---------------------------------------------------------------------------
# Mass density
# ---------------------------------------------------------------------------
def linear_density(mass: float, length: float, mass_center: float
                   ) -> tuple[float, float]:
    """Coefficients ``(a, b)`` of ``mu(x) = a + b x`` on ``[0, length]``.

    ``x`` is measured from the thick end; the density has the given total
    ``mass`` and balance point ``mass_center``.  It is non-negative only for
    ``length / 3 <= mass_center <= 2 length / 3``.
    """
    A = mass / length
    B = mass * mass_center / length**2
    return 4 * A - 6 * B, 6 * (2 * B - A) / length


@dataclass
class SectionMassModel:
    """Piecewise-linear mass density built from per-section mass data.

    Sections are ordered butt to tip.  Section ``i`` starts at
    ``sum(lengths[:i]) - i * ferrule_overlap`` from the butt, so neighbouring
    sections overlap at the ferrules, where their densities add.

    The fit parameters are each section's mass [kg] and balance point [m]
    (from the thick end of the section, as measured for swingweight).  For a
    finished rod (``has_reel_seat``) the butt section's measured values
    include the reel seat and grip, which are split off as a uniform
    cylinder of length ``l_rg`` following Løvoll & Angus (eqs. 6-8).

    Attributes:
        lengths: Section lengths, butt to tip [m].
        ferrule_overlap: Overlap per joint [m].
        masses: Measured (or guessed) section masses [kg].
        mass_centers: Measured (or guessed) balance points [m].
        mass_sigma: Prior standard deviation of the masses [kg]; ``None``
            leaves them unconstrained.
        mass_center_sigma: Prior standard deviation of the balance points
            [m]; ``None`` leaves them unconstrained.
        has_reel_seat: Model a reel seat + grip on the butt section.
        l_rg: Reel seat + grip length [m].
    """

    lengths: Sequence[float]
    ferrule_overlap: float
    masses: Sequence[float]
    mass_centers: Sequence[float]
    mass_sigma: float | None = 0.2e-3
    mass_center_sigma: float | None = 5e-3
    has_reel_seat: bool = False
    l_rg: float = L_RG_DEFAULT

    @classmethod
    def from_sections(cls, sections: Sequence[RodSection],
                      assembled_length: float, **kwargs
                      ) -> "SectionMassModel":
        """Build from :class:`~flycastsim.rod.swingweight.RodSection` data,
        with the ferrule overlap from the assembled length."""
        lengths = [s.length for s in sections]
        n_joints = max(len(sections) - 1, 1)
        overlap = (sum(lengths) - assembled_length) / n_joints
        return cls(lengths=lengths, ferrule_overlap=overlap,
                   masses=[s.mass for s in sections],
                   mass_centers=[s.mass_center for s in sections], **kwargs)

    @property
    def n_params(self) -> int:
        return 2 * len(self.lengths)

    @property
    def starts(self) -> np.ndarray:
        """Position of each section's thick end from the butt [m]."""
        lengths = np.asarray(self.lengths, dtype=float)
        i = np.arange(len(lengths))
        return np.concatenate([[0.0], np.cumsum(lengths)[:-1]]) \
            - i * self.ferrule_overlap

    @property
    def breakpoints(self) -> np.ndarray:
        """Section ends and ferrule positions, where the density jumps."""
        starts = self.starts
        ends = starts + np.asarray(self.lengths, dtype=float)
        points = np.concatenate([starts[1:], ends[:-1]])
        if self.has_reel_seat:
            points = np.append(points, self.l_rg)
        return np.unique(points)

    def initial_params(self) -> np.ndarray:
        """Parameter vector ``[m_1, x_1, m_2, x_2, ...]`` from the data."""
        return np.column_stack([self.masses, self.mass_centers]).ravel()

    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        """Parameter bounds: positive masses and balance points in
        ``[l/3, 2l/3]``, where the linear density is non-negative."""
        lengths = np.asarray(self.lengths, dtype=float)
        lo = np.column_stack([np.full_like(lengths, 1e-6), lengths / 3])
        hi = np.column_stack([np.full_like(lengths, np.inf), 2 * lengths / 3])
        if self.has_reel_seat:     # measured butt CoM includes reel seat
            lo[0, 1], hi[0, 1] = 0.0, lengths[0]
        return lo.ravel(), hi.ravel()

    def prior_residuals(self, params: np.ndarray) -> np.ndarray:
        """Normalised deviations of the parameters from the measurements."""
        p = np.asarray(params).reshape(-1, 2)
        out = []
        if self.mass_sigma is not None:
            out.append((p[:, 0] - np.asarray(self.masses)) / self.mass_sigma)
        if self.mass_center_sigma is not None:
            out.append((p[:, 1] - np.asarray(self.mass_centers))
                       / self.mass_center_sigma)
        return np.concatenate(out) if out else np.zeros(0)

    def density(self, params: np.ndarray | None = None):
        """Vectorised ``mu(s)`` [kg/m] for the given parameters."""
        p = (self.initial_params() if params is None
             else np.asarray(params)).reshape(-1, 2)
        lengths = np.asarray(self.lengths, dtype=float)
        starts = self.starts
        pieces = []          # (start, length, a, b)
        uniform = None       # reel seat + grip: (length, density)
        for i, (m, xc) in enumerate(p):
            if i == 0 and self.has_reel_seat:
                rsg = reel_seat_grip_correction(
                    RodSection(m, lengths[0], xc),
                    RodSection(p[1, 0], lengths[1], p[1, 1]), l_rg=self.l_rg)
                m, xc = rsg.blank_mass, rsg.x_bcm
                uniform = (self.l_rg, rsg.mass / self.l_rg)
            a, b = linear_density(m, lengths[i], xc)
            pieces.append((starts[i], lengths[i], a, b))

        def mu(s):
            s = np.asarray(s, dtype=float)
            out = np.zeros_like(s)
            for start, length, a, b in pieces:
                x = s - start
                # small tolerance: section ends are sums of lengths and
                # overlaps, and the rod tip must not fall outside by round-off
                inside = (x >= -1e-9) & (x <= length + 1e-9)
                out = out + np.where(inside, a + b * x, 0.0)
            if uniform is not None:
                out = out + np.where(s <= uniform[0], uniform[1], 0.0)
            return out

        return mu


# ---------------------------------------------------------------------------
# Bending stiffness
# ---------------------------------------------------------------------------
@dataclass
class MonotoneLogEI:
    """Non-increasing cubic B-spline in :math:`\\log EI` over the free length.

    The spline coefficients are ``c_0 = p_0`` and
    ``c_{i+1} = c_i - exp(p_{i+1})``; a B-spline with non-increasing
    coefficients is itself non-increasing (variation diminishing), so every
    parameter vector gives a monotone stiffness while the fit stays
    unconstrained.  ``EI`` is held at ``EI(s_clamp)`` behind the clamp and at
    ``EI(length)`` beyond the tip.

    Attributes:
        s_clamp: Start of the spline (clamp position from the butt) [m].
        length: End of the spline (rod tip) [m].
        n_coef: Number of spline coefficients (= parameters).
        degree: Spline degree.
        max_log_step: Largest drop in :math:`\\log EI` between neighbouring
            coefficients (keeps trial steps physical).
    """

    s_clamp: float
    length: float
    n_coef: int = 8
    degree: int = 3
    max_log_step: float = 2.0
    knots: np.ndarray = field(init=False, repr=False)

    def __post_init__(self):
        n_inner = self.n_coef - self.degree - 1
        if n_inner < 0:
            raise ValueError("n_coef must be at least degree + 1")
        inner = np.linspace(self.s_clamp, self.length, n_inner + 2)[1:-1]
        self.knots = np.concatenate([[self.s_clamp] * (self.degree + 1), inner,
                                     [self.length] * (self.degree + 1)])

    @property
    def n_params(self) -> int:
        return self.n_coef

    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        """Parameter bounds: ``EI(s_clamp)`` in [0.01, 1e4] N m^2 and each
        coefficient drop in ``[e^-30, max_log_step]``."""
        lo = np.concatenate([[np.log(1e-2)], np.full(self.n_coef - 1, -30.0)])
        hi = np.concatenate([[np.log(1e4)],
                             np.full(self.n_coef - 1, np.log(self.max_log_step))])
        return lo, hi

    def coefficients(self, params: np.ndarray) -> np.ndarray:
        """Spline coefficients of :math:`\\log EI` for ``params``."""
        p = np.asarray(params, dtype=float)
        return p[0] - np.concatenate([[0.0], np.cumsum(np.exp(p[1:]))])

    @property
    def greville(self) -> np.ndarray:
        """Greville abscissae: the positions the coefficients belong to."""
        k = self.degree
        return np.array([self.knots[j + 1:j + 1 + k].mean()
                         for j in range(self.n_coef)])

    def params_from_coefficients(self, coef: np.ndarray) -> np.ndarray:
        """Parameters for strictly decreasing spline coefficients."""
        coef = np.asarray(coef, dtype=float)
        return np.concatenate([[coef[0]], np.log(-np.diff(coef))])

    def params_from_endpoints(self, EI_clamp: float, EI_tip: float
                              ) -> np.ndarray:
        """Parameters of an exact exponential taper between the end values.

        A B-spline reproduces a linear function when its coefficients are
        that function sampled at the Greville abscissae.
        """
        g = (self.greville - self.s_clamp) / (self.length - self.s_clamp)
        coef = np.log(EI_clamp) + g * (np.log(EI_tip) - np.log(EI_clamp))
        return self.params_from_coefficients(coef)

    def stiffness(self, params: np.ndarray):
        """Vectorised ``EI(s)`` [N m^2] for the given parameters."""
        spline = BSpline(self.knots, self.coefficients(params), self.degree,
                         extrapolate=False)
        lo, hi = self.s_clamp, self.length

        def EI(s):
            return np.exp(spline(np.clip(np.asarray(s, dtype=float), lo, hi)))

        return EI

    def smoothness_residuals(self, params: np.ndarray) -> np.ndarray:
        """Second divided differences of the coefficients over the Greville
        abscissae, scaled by the free length squared (dimensionless); zero
        for an exponential taper."""
        g = self.greville
        slope = np.diff(self.coefficients(params)) / np.diff(g)
        curv = np.diff(slope) / (0.5 * (g[2:] - g[:-2]))
        return curv * (self.length - self.s_clamp) ** 2


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
@dataclass
class BendFrame:
    """One static bend observation.

    Attributes:
        points: Observed centre-line points ``(N, 2)`` relative to the clamp,
            ``y`` up [m].
        load_steps: Number of load steps on the tip; the tip mass is
            ``known_mass + load_steps * load_step``.
        tip: Observed tip position ``(2,)`` [m], or ``None``.
        known_mass: Tip mass known in absolute terms [kg].
        clamp_angle: Clamp angle above the horizontal [rad].
    """

    points: np.ndarray
    load_steps: float = 0.0
    tip: np.ndarray | None = None
    known_mass: float = 0.0
    clamp_angle: float = 0.0


@dataclass
class FrequencyData:
    """Fundamental frequency [Hz] vs. tip mass [kg], with uncertainty [Hz]."""

    tip_masses: np.ndarray
    frequencies: np.ndarray
    sigma: float = 0.01


@dataclass
class CCSData:
    """Common Cents System point: tip mass ``ip_mass`` [kg] gives a vertical
    tip deflection of ``deflection_fraction`` times the free length (with
    uncertainty ``sigma`` in the same fraction units)."""

    ip_mass: float
    deflection_fraction: float = 1.0 / 3.0
    sigma: float = 0.01


@dataclass
class ImageTransform:
    """Map image pixels to metres relative to the clamp (``y`` up).

    A pixel ``p`` maps to ``scale * R(-roll) @ mirror(p - clamp_px)``, where
    the image ``y`` axis is flipped to point up and, for a rod pointing left
    in the image, ``x`` is mirrored so the rod points along ``+x``.  ``roll``
    is the camera roll (tilt of the image horizontal against the true
    horizontal).  The fit also estimates a clamp-angle offset, the deviation
    of the clamp from the angle given in each frame.

    The attributes are the initial values.  The five fit parameters are
    *changes* from them, ``[dcx, dcy, dlog(scale), roll, clamp_angle_offset]``
    (so ``least_squares``' relative step tolerance is not dominated by the
    clamp's pixel coordinates), each with a Gaussian prior around zero
    (``None`` sigma = no prior); :meth:`fitted` returns the transform with
    the fitted values.  Observed points are compared with the model in
    pixels, with uncertainty ``sigma_px``.

    Attributes:
        clamp_px: Clamp point in the image ``(x, y)`` [px].
        scale: Pixel scale [m/px].
        roll: Camera roll [rad].
        clamp_angle_offset: Clamp-angle offset [rad].
        rod_points_left: The rod points towards decreasing image ``x``.
        sigma_px: Uncertainty of traced points [px].
        clamp_sigma_px: Prior sigma of the clamp position [px].
        scale_sigma_rel: Relative prior sigma of the scale.
        roll_sigma: Prior sigma of the camera roll [rad].
        clamp_angle_sigma: Prior sigma of the clamp-angle offset [rad].
    """

    clamp_px: np.ndarray
    scale: float
    roll: float = 0.0
    clamp_angle_offset: float = 0.0
    rod_points_left: bool = True
    sigma_px: float = 1.0
    clamp_sigma_px: float | None = 20.0
    scale_sigma_rel: float | None = 0.02
    roll_sigma: float | None = np.radians(1.0)
    clamp_angle_sigma: float | None = np.radians(3.0)

    n_params = 5

    def initial_params(self) -> np.ndarray:
        return np.array([0.0, 0.0, 0.0, self.roll, self.clamp_angle_offset])

    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        return (np.array([-500.0, -500.0, -1.0, -0.3, -0.5]),
                np.array([500.0, 500.0, 1.0, 0.3, 0.5]))

    def _absolute(self, params):
        dcx, dcy, dlog, roll, _ = params
        return (self.clamp_px[0] + dcx, self.clamp_px[1] + dcy,
                self.scale * np.exp(dlog), roll)

    def fitted(self, params: np.ndarray) -> "ImageTransform":
        """Copy with the absolute values for ``params`` as initial values."""
        cx, cy, scale, roll = self._absolute(params)
        return replace(self, clamp_px=np.array([cx, cy]), scale=float(scale),
                       roll=float(roll),
                       clamp_angle_offset=float(params[4]))

    def to_physical(self, params: np.ndarray, pixels: np.ndarray
                    ) -> np.ndarray:
        """Pixels ``(N, 2)`` to metres relative to the clamp, ``y`` up."""
        cx, cy, scale, roll = self._absolute(params)
        p = np.atleast_2d(pixels).astype(float)
        u = np.column_stack([p[:, 0] - cx, cy - p[:, 1]])
        if self.rod_points_left:
            u[:, 0] = -u[:, 0]
        c, s = np.cos(roll), np.sin(roll)
        return scale * np.column_stack(
            [c * u[:, 0] + s * u[:, 1], -s * u[:, 0] + c * u[:, 1]])

    def to_pixels(self, params: np.ndarray, points: np.ndarray) -> np.ndarray:
        """Inverse of :meth:`to_physical`."""
        cx, cy, scale, roll = self._absolute(params)
        q = np.atleast_2d(points).astype(float) / scale
        c, s = np.cos(roll), np.sin(roll)
        u = np.column_stack([c * q[:, 0] - s * q[:, 1],
                             s * q[:, 0] + c * q[:, 1]])
        if self.rod_points_left:
            u[:, 0] = -u[:, 0]
        return np.column_stack([cx + u[:, 0], cy - u[:, 1]])

    def pixel_size(self, params: np.ndarray) -> float:
        """Pixel scale [m/px] for ``params``."""
        return float(self._absolute(params)[2])

    def prior_residuals(self, params: np.ndarray) -> np.ndarray:
        p0 = self.initial_params()
        sig = [self.clamp_sigma_px, self.clamp_sigma_px,
               self.scale_sigma_rel, self.roll_sigma, self.clamp_angle_sigma]
        return np.array([(p - q) / s for p, q, s in zip(params, p0, sig)
                         if s is not None])


# ---------------------------------------------------------------------------
# Fit
# ---------------------------------------------------------------------------
def project_onto_curve(sol: ElasticaSolution, points: np.ndarray,
                       n_samples: int = 400, n_newton: int = 6
                       ) -> tuple[np.ndarray, np.ndarray]:
    """Closest-point projection of ``points`` onto a solved rod curve.

    Starts from the nearest of ``n_samples`` curve samples and refines with
    Gauss--Newton steps along the unit tangent (the rod is inextensible, so
    ``d r / d s`` is the unit tangent).

    Returns:
        ``(s, distance)``: arc length of the closest points and the signed
        normal distance (positive to the left of the tangent) [m].
    """
    pts = np.atleast_2d(points)
    s_grid = np.linspace(sol.s_clamp, sol.length, n_samples)
    xy = sol.at(s_grid)[:2].T
    nearest = np.argmin(((pts[:, None, :] - xy[None, :, :]) ** 2).sum(-1),
                        axis=1)
    s = s_grid[nearest]
    for _ in range(n_newton):
        x, y, theta, _m = sol.at(s)
        dx, dy = pts[:, 0] - x, pts[:, 1] - y
        s = np.clip(s + dx * np.cos(theta) + dy * np.sin(theta),
                    sol.s_clamp, sol.length)
    x, y, theta, _m = sol.at(s)
    dist = -(pts[:, 0] - x) * np.sin(theta) + (pts[:, 1] - y) * np.cos(theta)
    return s, dist


@dataclass
class ProfileFitProblem:
    """Everything needed for :func:`fit_profile`.

    Attributes:
        ei_model: Stiffness parametrisation.
        mass_model: Mass parametrisation (with its priors).
        length: Rod length [m].
        s_clamp: Clamp position from the butt [m].
        frames: Static bend observations.
        load_step: Load step per ``load_steps`` unit [kg] -- the initial
            guess if ``fit_load_step``.
        fit_load_step: Treat ``load_step`` as unknown.
        fit_frame_loads: Instead of one load step, fit each frame's added
            tip mass as its own unknown (for load sequences whose steps
            are not constant), starting from ``load_steps * load_step``.
            The absolute scale then comes from the frequency and CCS data
            and the section masses.  Overrides ``fit_load_step``.
        sigma_xy: Uncertainty of observed centre-line points [m].
        frequency: Tip-mass frequency data, or ``None``.
        ccs: CCS point, or ``None``.
        smoothness: Weight of the :math:`\\log EI` smoothness penalty.
        gravity: Gravitational acceleration [m/s^2].
        transform: If given, frame points and tips are image pixels mapped
            by this (fitted) :class:`ImageTransform`, and ``sigma_xy`` is
            replaced by its ``sigma_px``.
        robust: Residual scale [sigma] above which centre-line and tip
            residuals are down-weighted (``soft_l1``-like); ``None`` keeps
            plain least squares.
        clamp_compliance: Rotational compliance of the bend-test mount
            [rad/(N m)], see
            :func:`~flycastsim.rod.elastica.solve_cantilever_fd` -- the
            initial guess if ``fit_clamp_compliance``.  Not applied to the
            CCS point.
        fit_clamp_compliance: Treat ``clamp_compliance`` as unknown.
        frequency_elements: Beam elements for the frequency model.  Few
            are needed (cubic Hermite elements converge as ``h^4``), and
            more make the eigenproblem's round-off visible in the
            finite-difference Jacobian when ``EI`` spans a wide range.
    """

    ei_model: MonotoneLogEI
    mass_model: SectionMassModel
    length: float
    s_clamp: float
    frames: Sequence[BendFrame] = ()
    load_step: float = 0.0
    fit_load_step: bool = True
    fit_frame_loads: bool = False
    sigma_xy: float = 1e-3
    frequency: FrequencyData | None = None
    ccs: CCSData | None = None
    smoothness: float = 0.1
    gravity: float = GRAVITY
    transform: ImageTransform | None = None
    robust: float | None = None
    clamp_compliance: float = 0.0
    fit_clamp_compliance: bool = False
    frequency_elements: int = 24
    _cache: dict = field(default_factory=dict, init=False, repr=False)

    # -- parameter vector: [EI | log(load_step) or log(frame loads) | mass |
    #                        compliance? | transform?]
    def _load_mode(self) -> str:
        if self.fit_frame_loads:
            return "frames"
        return "step" if self.fit_load_step else "fixed"

    def initial_frame_loads(self) -> np.ndarray:
        """Initial added tip mass per frame [kg] (floored at 0.1 g)."""
        return np.maximum([f.load_steps * self.load_step
                           for f in self.frames], 1e-4)

    def _split(self, x):
        """Unpack ``x`` into ``(ei, added_masses, mass, compliance,
        transform)``; ``added_masses`` is the added tip mass per frame."""
        n_ei = self.ei_model.n_params
        n_m = self.mass_model.n_params
        ei_p = x[:n_ei]
        i = n_ei
        mode = self._load_mode()
        steps = np.array([f.load_steps for f in self.frames], dtype=float)
        if mode == "frames":
            added = np.exp(x[i:i + len(self.frames)])
            i += len(self.frames)
        elif mode == "step":
            added = steps * float(np.exp(x[i]))
            i += 1
        else:
            added = steps * self.load_step
        mass_p = x[i:i + n_m]
        i += n_m
        if self.fit_clamp_compliance:
            compliance = float(x[i])
            i += 1
        else:
            compliance = self.clamp_compliance
        tr_p = x[i:] if self.transform is not None else None
        return ei_p, added, mass_p, compliance, tr_p

    def pack(self, ei_params, load_step, mass_params,
             transform_params=None) -> np.ndarray:
        parts = [np.asarray(ei_params, dtype=float)]
        mode = self._load_mode()
        if mode == "frames":
            parts.append(np.log(self.initial_frame_loads()))
        elif mode == "step":
            parts.append([np.log(load_step)])
        parts.append(np.asarray(mass_params, dtype=float))
        if self.fit_clamp_compliance:
            parts.append([self.clamp_compliance])
        if self.transform is not None:
            parts.append(self.transform.initial_params()
                         if transform_params is None
                         else np.asarray(transform_params, dtype=float))
        return np.concatenate(parts)

    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        """Bounds on the packed parameter vector."""
        lo, hi = zip(self.ei_model.bounds(), self.mass_model.bounds())
        lo, hi = list(lo), list(hi)
        n_load = {"frames": len(self.frames), "step": 1,
                  "fixed": 0}[self._load_mode()]
        if n_load:
            lo.insert(1, np.full(n_load, np.log(1e-6)))
            hi.insert(1, np.full(n_load, np.log(10.0)))
        if self.fit_clamp_compliance:
            lo.append([0.0])
            hi.append([1.0])
        if self.transform is not None:
            t_lo, t_hi = self.transform.bounds()
            lo.append(t_lo)
            hi.append(t_hi)
        return np.concatenate(lo), np.concatenate(hi)

    def jac_sparsity(self, n_residuals: int) -> np.ndarray | None:
        """Jacobian sparsity pattern when frame loads are fitted.

        Each frame's load only affects that frame's residuals (which come
        first, frame by frame), so finite differences can perturb all frame
        loads in one evaluation.  ``None`` if frame loads are not fitted.
        """
        if self._load_mode() != "frames":
            return None
        n_frames = len(self.frames)
        n_par = len(self.pack(self.ei_model.params_from_endpoints(2.0, 1.0),
                              self.load_step,
                              self.mass_model.initial_params()))
        pattern = np.ones((n_residuals, n_par), dtype=bool)
        col0 = self.ei_model.n_params
        pattern[:, col0:col0 + n_frames] = False
        row = 0
        for k, frame in enumerate(self.frames):
            n = len(frame.points) + (0 if frame.tip is None else 2)
            pattern[row:row + n, col0 + k] = True
            row += n
        return pattern

    def _robust(self, r: np.ndarray) -> np.ndarray:
        """Down-weight large residuals (outliers such as a mistraced tip).

        Returns ``sign(r) c sqrt(2 (sqrt(1 + (r/c)^2) - 1))``, whose square
        is the ``soft_l1`` loss with scale ``c``: quadratic for small ``r``,
        linear for large.
        """
        if self.robust is None:
            return r
        c = self.robust
        return np.sign(r) * c * np.sqrt(2 * (np.sqrt(1 + (r / c) ** 2) - 1))

    def _solve(self, key, EI, mu, tip_mass, clamp_angle, compliance=0.0):
        sol = solve_cantilever_fd(EI, mu, length=self.length,
                                  s_clamp=self.s_clamp,
                                  tip_load=tip_mass * self.gravity,
                                  clamp_angle=clamp_angle,
                                  clamp_compliance=compliance,
                                  gravity=self.gravity,
                                  guess=self._cache.get(key))
        self._cache[key] = sol
        return sol

    def residuals(self, x: np.ndarray) -> np.ndarray:
        """Stacked, normalised residual vector for parameters ``x``."""
        ei_p, added, mass_p, compliance, tr_p = self._split(
            np.asarray(x, dtype=float))
        EI = self.ei_model.stiffness(ei_p)
        mu = self.mass_model.density(mass_p)
        if tr_p is None:
            def to_m(p):
                return np.atleast_2d(p)
            unit, angle_offset = self.sigma_xy, 0.0
        else:
            def to_m(p):
                return self.transform.to_physical(tr_p, p)
            unit = self.transform.pixel_size(tr_p) * self.transform.sigma_px
            angle_offset = tr_p[4]
        out = []
        for k, frame in enumerate(self.frames):
            tip_mass = frame.known_mass + added[k]
            n = len(frame.points) + (0 if frame.tip is None else 2)
            try:
                sol = self._solve(("frame", k), EI, mu, tip_mass,
                                  frame.clamp_angle + angle_offset,
                                  compliance)
            except ElasticaError:
                out.append(np.full(n, 1e3))
                continue
            out.append(self._robust(
                project_onto_curve(sol, to_m(frame.points))[1] / unit))
            if frame.tip is not None:
                out.append(self._robust(
                    (np.asarray(sol.tip) - to_m(frame.tip)[0]) / unit))
        if self.frequency is not None:
            f = frequency_vs_tip_mass(
                EI, mu, self.frequency.tip_masses, length=self.length,
                s_clamp=self.s_clamp, n_elements=self.frequency_elements,
                breakpoints=self.mass_model.breakpoints)
            out.append((f - self.frequency.frequencies)
                       / self.frequency.sigma)
        if self.ccs is not None:
            try:
                sol = self._solve("ccs", EI, mu, self.ccs.ip_mass, 0.0)
                frac = -sol.tip[1] / sol.free_length
                out.append([(frac - self.ccs.deflection_fraction)
                            / self.ccs.sigma])
            except ElasticaError:
                out.append([1e3])
        out.append(self.mass_model.prior_residuals(mass_p))
        if tr_p is not None:
            out.append(self.transform.prior_residuals(tr_p))
        out.append(self.smoothness * self.ei_model.smoothness_residuals(ei_p))
        return np.concatenate([np.atleast_1d(np.asarray(r, dtype=float))
                               for r in out])


@dataclass
class ProfileFitResult:
    """Outcome of :func:`fit_profile`.

    Attributes:
        problem: The fitted problem.
        x: Optimal parameter vector.
        ei_params: Stiffness parameters.
        load_step: Fitted (or fixed) load step [kg], ``nan`` when frame
            loads are fitted individually.
        frame_loads: Added tip mass per frame [kg].
        mass_params: Mass parameters ``[m_1, x_1, ...]``.
        transform_params: Fitted image-transform parameters, or ``None``.
        clamp_compliance: Fitted (or fixed) mount compliance [rad/(N m)].
        EI: Fitted ``EI(s)`` [N m^2].
        mu: Fitted ``mu(s)`` [kg/m].
        optimize: The :func:`scipy.optimize.least_squares` result.
    """

    problem: ProfileFitProblem
    x: np.ndarray
    ei_params: np.ndarray
    load_step: float
    frame_loads: np.ndarray
    mass_params: np.ndarray
    transform_params: np.ndarray | None
    clamp_compliance: float
    EI: object
    mu: object
    optimize: object

    def table(self, n: int = 41) -> dict[str, np.ndarray]:
        """Profiles on ``n`` points from butt to tip, in the column layout
        of the FEM rod CSVs (``s_m``, ``m_kg_per_m``, ``EI_Nm2``)."""
        s = np.linspace(0.0, self.problem.length, n)
        return {"s_m": s, "m_kg_per_m": self.mu(s), "EI_Nm2": self.EI(s)}

    def summary(self) -> dict:
        """Fitted quantities as plain JSON-serialisable values (SI units)."""
        prob = self.problem
        res = self.optimize
        out = {
            "length_m": prob.length,
            "s_clamp_m": prob.s_clamp,
            "cost": float(res.cost),
            "n_residuals": int(res.fun.size),
            "n_evaluations": int(res.nfev),
            "status": res.message,
            "frame_load_steps": [float(f.load_steps) for f in prob.frames],
            "frame_added_mass_kg": [float(m) for m in self.frame_loads],
            "load_step_kg": (None if np.isnan(self.load_step)
                             else float(self.load_step)),
            "clamp_compliance_rad_per_Nm": float(self.clamp_compliance),
            "section_mass_kg": [float(v) for v in self.mass_params[0::2]],
            "section_mass_center_m": [float(v)
                                      for v in self.mass_params[1::2]],
            "ei_spline_params": [float(v) for v in self.ei_params],
        }
        if self.transform_params is not None:
            fit = prob.transform.fitted(self.transform_params)
            out["image_transform"] = {
                "clamp_px": [float(v) for v in fit.clamp_px],
                "scale_m_per_px": fit.scale,
                "camera_roll_rad": fit.roll,
                "clamp_angle_offset_rad": fit.clamp_angle_offset,
            }
        return out

    def write_component(self, folder: str | Path, name: str, *,
                        n_points: int = 41, n_nodes: int = 31,
                        notes: Sequence[str] = ()) -> Path:
        """Write the fitted rod as an FEM component (``rod.json`` +
        ``rod.csv``) loadable with
        :func:`flycastsim.fem.components.load_component`.

        The CSV has columns ``s_m, m_kg_per_m, EI_Nm2`` (no diameter: the
        fit does not measure it, so the component has ``d = 0`` and no air
        drag unless a ``d_m`` column is added); ``notes`` become ``#``
        comment lines at its top.

        Returns:
            Path of the written ``rod.json``.
        """
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        table = self.table(n_points)
        header = "".join(f"# {line}\n" for line in notes)
        rows = "\n".join(f"{s:.6g},{m:.6g},{ei:.6g}" for s, m, ei in zip(
            table["s_m"], table["m_kg_per_m"], table["EI_Nm2"]))
        (folder / "rod.csv").write_text(
            header + "s_m,m_kg_per_m,EI_Nm2\n" + rows + "\n")
        meta = {
            "name": name,
            "kind": "rod",
            "length_m": float(self.problem.length),
            "n_nodes": int(n_nodes),
            "profile_csv": "rod.csv",
            "columns": {"s": "s_m", "m": "m_kg_per_m", "EI": "EI_Nm2"},
            "mass_mode": "absolute",
            "eta_s": 0.0,
            "interp": "linear",
        }
        path = folder / "rod.json"
        path.write_text(json.dumps(meta, indent=2) + "\n")
        return path


def fit_profile(problem: ProfileFitProblem,
                ei_params: np.ndarray | None = None,
                mass_params: np.ndarray | None = None,
                **least_squares_kwargs) -> ProfileFitResult:
    """Joint least-squares fit of the stiffness and mass profiles.

    Args:
        problem: Data, parametrisations and weights.
        ei_params: Initial stiffness parameters (default: an exponential
            taper from 30 to 1 N m^2).
        mass_params: Initial mass parameters (default: the measurements).
        **least_squares_kwargs: Passed to :func:`scipy.optimize.least_squares`
            (defaults ``x_scale="jac"``, ``xtol = ftol = 1e-10``,
            ``diff_step = 1e-5`` and the parameter bounds of the models).
    """
    if ei_params is None:
        ei_params = problem.ei_model.params_from_endpoints(30.0, 1.0)
    if mass_params is None:
        mass_params = problem.mass_model.initial_params()
    if problem._load_mode() != "fixed" and not problem.load_step > 0:
        raise ValueError("fitted loads need a positive load_step guess")
    x0 = problem.pack(ei_params, problem.load_step, mass_params)
    least_squares_kwargs.setdefault("x_scale", "jac")
    # The problem is ill-conditioned (stiffness near the tip has little
    # leverage), so the default tolerances stop too early.
    for key in ("xtol", "ftol"):
        least_squares_kwargs.setdefault(key, 1e-10)
    # Relative finite-difference step: the default (~1.5e-8) amplifies the
    # residuals' round-off noise enough to stall the fit.
    least_squares_kwargs.setdefault("diff_step", 1e-5)
    lo, hi = problem.bounds()
    least_squares_kwargs.setdefault("bounds", (lo, hi))
    x0 = np.clip(x0, lo, hi)
    sparsity = problem.jac_sparsity(len(problem.residuals(x0)))
    if sparsity is not None:
        least_squares_kwargs.setdefault("jac_sparsity", sparsity)
    res = least_squares(problem.residuals, x0, **least_squares_kwargs)
    ei_p, added, mass_p, compliance, tr_p = problem._split(res.x)
    mode = problem._load_mode()
    load_step = (float("nan") if mode == "frames" else
                 float(np.exp(res.x[problem.ei_model.n_params]))
                 if mode == "step" else problem.load_step)
    return ProfileFitResult(problem=problem, x=res.x, ei_params=ei_p,
                            load_step=load_step, frame_loads=added,
                            mass_params=mass_p,
                            transform_params=tr_p,
                            clamp_compliance=compliance,
                            EI=problem.ei_model.stiffness(ei_p),
                            mu=problem.mass_model.density(mass_p),
                            optimize=res)
