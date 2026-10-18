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

from collections.abc import Sequence
from dataclasses import dataclass, field

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
                inside = (x >= 0) & (x <= length)
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
        sigma_xy: Uncertainty of observed centre-line points [m].
        frequency: Tip-mass frequency data, or ``None``.
        ccs: CCS point, or ``None``.
        smoothness: Weight of the :math:`\\log EI` smoothness penalty.
        gravity: Gravitational acceleration [m/s^2].
    """

    ei_model: MonotoneLogEI
    mass_model: SectionMassModel
    length: float
    s_clamp: float
    frames: Sequence[BendFrame] = ()
    load_step: float = 0.0
    fit_load_step: bool = True
    sigma_xy: float = 1e-3
    frequency: FrequencyData | None = None
    ccs: CCSData | None = None
    smoothness: float = 0.1
    gravity: float = GRAVITY
    _cache: dict = field(default_factory=dict, init=False, repr=False)

    # -- parameter vector: [EI | log(load_step)? | mass] -------------------
    def _split(self, x):
        n_ei = self.ei_model.n_params
        ei_p = x[:n_ei]
        if self.fit_load_step:
            load_step = float(np.exp(x[n_ei]))
            mass_p = x[n_ei + 1:]
        else:
            load_step = self.load_step
            mass_p = x[n_ei:]
        return ei_p, load_step, mass_p

    def pack(self, ei_params, load_step, mass_params) -> np.ndarray:
        parts = [np.asarray(ei_params, dtype=float)]
        if self.fit_load_step:
            parts.append([np.log(load_step)])
        parts.append(np.asarray(mass_params, dtype=float))
        return np.concatenate(parts)

    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        """Bounds on the packed parameter vector."""
        ei_lo, ei_hi = self.ei_model.bounds()
        m_lo, m_hi = self.mass_model.bounds()
        mid_lo = [np.log(1e-6)] if self.fit_load_step else []
        mid_hi = [np.log(10.0)] if self.fit_load_step else []
        return (np.concatenate([ei_lo, mid_lo, m_lo]),
                np.concatenate([ei_hi, mid_hi, m_hi]))

    def _solve(self, key, EI, mu, tip_mass, clamp_angle):
        sol = solve_cantilever_fd(EI, mu, length=self.length,
                                  s_clamp=self.s_clamp,
                                  tip_load=tip_mass * self.gravity,
                                  clamp_angle=clamp_angle,
                                  gravity=self.gravity,
                                  guess=self._cache.get(key))
        self._cache[key] = sol
        return sol

    def residuals(self, x: np.ndarray) -> np.ndarray:
        """Stacked, normalised residual vector for parameters ``x``."""
        ei_p, load_step, mass_p = self._split(np.asarray(x, dtype=float))
        EI = self.ei_model.stiffness(ei_p)
        mu = self.mass_model.density(mass_p)
        out = []
        for k, frame in enumerate(self.frames):
            tip_mass = frame.known_mass + frame.load_steps * load_step
            n = len(frame.points) + (0 if frame.tip is None else 2)
            try:
                sol = self._solve(("frame", k), EI, mu, tip_mass,
                                  frame.clamp_angle)
            except ElasticaError:
                out.append(np.full(n, 1e3))
                continue
            out.append(project_onto_curve(sol, frame.points)[1]
                       / self.sigma_xy)
            if frame.tip is not None:
                out.append((np.asarray(sol.tip) - frame.tip) / self.sigma_xy)
        if self.frequency is not None:
            f = frequency_vs_tip_mass(
                EI, mu, self.frequency.tip_masses, length=self.length,
                s_clamp=self.s_clamp,
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
        load_step: Fitted (or fixed) load step [kg].
        mass_params: Mass parameters ``[m_1, x_1, ...]``.
        EI: Fitted ``EI(s)`` [N m^2].
        mu: Fitted ``mu(s)`` [kg/m].
        optimize: The :func:`scipy.optimize.least_squares` result.
    """

    problem: ProfileFitProblem
    x: np.ndarray
    ei_params: np.ndarray
    load_step: float
    mass_params: np.ndarray
    EI: object
    mu: object
    optimize: object

    def table(self, n: int = 41) -> dict[str, np.ndarray]:
        """Profiles on ``n`` points from butt to tip, in the column layout
        of the FEM rod CSVs (``s_m``, ``m_kg_per_m``, ``EI_Nm2``)."""
        s = np.linspace(0.0, self.problem.length, n)
        return {"s_m": s, "m_kg_per_m": self.mu(s), "EI_Nm2": self.EI(s)}


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
    if problem.fit_load_step and not problem.load_step > 0:
        raise ValueError("fit_load_step needs a positive load_step guess")
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
    res = least_squares(problem.residuals, x0, **least_squares_kwargs)
    ei_p, load_step, mass_p = problem._split(res.x)
    return ProfileFitResult(problem=problem, x=res.x, ei_params=ei_p,
                            load_step=load_step, mass_params=mass_p,
                            EI=problem.ei_model.stiffness(ei_p),
                            mu=problem.mass_model.density(mass_p),
                            optimize=res)
