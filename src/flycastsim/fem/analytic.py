"""Closed-form reference solutions for the verification test cases.

These analytic solutions correspond to the simplified verification problems
described on the willmanco.se *Verification* page and in the paper's Online
Resource 1.  They are used by the test-suite to confirm that the numerical
engine solves the equations accurately (and with second-order convergence).
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import brentq
from scipy.special import j0, jn_zeros


# --- Static cases -----------------------------------------------------------

def cantilever_tip_load(s: np.ndarray, EI: float, P: float,
                        L: float) -> np.ndarray:
    """Small-deflection cantilever with a transverse tip load ``P``.

    Clamped at ``s = 0`` (``y = 0``, ``y' = 0``), point load ``P`` at the
    free tip ``s = L``.  Euler-Bernoulli theory gives

        y(s) = P * s^2 * (3 L - s) / (6 EI).

    Returns the transverse deflection ``y(s)``.
    """
    return P * s ** 2 * (3.0 * L - s) / (6.0 * EI)


def cantilever_udl(s: np.ndarray, EI: float, w: float,
                   L: float) -> np.ndarray:
    """Small-deflection cantilever under a uniform transverse load ``w``.

        y(s) = w * s^2 * (6 L^2 - 4 L s + s^2) / (24 EI).
    """
    return w * s ** 2 * (6.0 * L ** 2 - 4.0 * L * s + s ** 2) / (24.0 * EI)


def catenary_hanging_chain(x: np.ndarray, a: float, x0: float,
                           y0: float) -> np.ndarray:
    """Catenary ``y = y0 + a*(cosh((x - x0)/a) - 1)``.

    ``a = H / (m g)`` where ``H`` is the (constant) horizontal tension.
    """
    return y0 + a * (np.cosh((x - x0) / a) - 1.0)


def catenary_by_arclength(s: np.ndarray, a: float, x0: float, m: float,
                          g: float):
    """Catenary parameterised by arc length ``s`` measured from the left end.

    A uniform chain of weight per length ``w = m g`` hangs between two points
    and forms the catenary ``y = a cosh(x / a)`` with constant horizontal
    tension ``H = w a``.  The chain spans ``x in [-x0, x0]`` so its total
    length is ``L = 2 a sinh(x0 / a)``.

    For a point a horizontal distance ``x`` from the lowest point the arc
    length from the left end is ``s = a (sinh(x/a) + sinh(x0/a))``, which is
    inverted analytically below.

    Args:
        s: Arc-length coordinates (``0 <= s <= L``).
        a: Catenary parameter ``H / (m g)`` (radius of curvature at the apex).
        x0: Half-span; the chain runs from ``x = -x0`` to ``x = +x0``.
        m: Mass per unit length.
        g: Gravitational acceleration.

    Returns:
        Tuple ``(x, y, phi, nu, F_s)`` of arrays giving, along the chain, the
        horizontal/vertical coordinates, the tangent angle ``phi`` (from the
        ``+x`` axis), the curvature ``nu = d phi / ds`` and the tangential
        (tension) force ``F_s``.
    """
    w = m * g
    sh = s / a - np.sinh(x0 / a)
    x = a * np.arcsinh(sh)
    y = a * np.cosh(x / a)
    phi = np.arctan(np.sinh(x / a))
    nu = np.cos(phi) / y
    F_s = w * y
    return x, y, phi, nu, F_s


def towed_line_tension(s: np.ndarray, m: float, g: float, T_tip: float,
                       L: float) -> np.ndarray:
    """Tension along a vertical line under gravity held from the top.

    With arc length ``s`` measured from the top and a tension ``T_tip`` at
    the bottom (``s = L``), static balance gives

        T(s) = T_tip + m * g * (L - s).
    """
    return T_tip + m * g * (L - s)


# --- Dynamic cases ----------------------------------------------------------

def beam_eigenfrequencies(EI: float, m: float, L: float,
                          n: int = 4, bc: str = "pinned") -> np.ndarray:
    """Natural angular frequencies of a uniform Euler-Bernoulli beam.

    Args:
        EI: Bending stiffness.
        m: Mass per unit length.
        L: Length.
        n: Number of modes to return.
        bc: ``"pinned"`` (simply supported), ``"clamped-free"`` (cantilever)
            or ``"free-free"``.

    Returns:
        Array of angular frequencies ``omega`` [rad/s].
    """
    if bc == "pinned":
        k = np.arange(1, n + 1) * np.pi
    elif bc == "clamped-free":
        # Roots of cos(b) cosh(b) + 1 = 0.
        k = _beam_roots(lambda b: np.cos(b) * np.cosh(b) + 1.0, n)
    elif bc == "free-free":
        # Roots of cos(b) cosh(b) - 1 = 0 (non-trivial).
        k = _beam_roots(lambda b: np.cos(b) * np.cosh(b) - 1.0, n)
    else:
        raise ValueError(f"unknown bc {bc!r}")
    beta = k / L
    return beta ** 2 * np.sqrt(EI / m)


def _beam_roots(fun, n: int) -> np.ndarray:
    """First ``n`` positive roots of ``fun`` (bracketed scan + brentq)."""
    roots = []
    b = 1e-3
    step = 0.05
    prev = fun(b)
    while len(roots) < n:
        b_next = b + step
        cur = fun(b_next)
        if np.isfinite(prev) and np.isfinite(cur) and prev * cur < 0:
            roots.append(brentq(fun, b, b_next))
        b, prev = b_next, cur
        if b > 1e3:
            break
    return np.array(roots)


def string_wave_speed(T: float, m: float) -> float:
    """Transverse wave speed on a taut string, ``c = sqrt(T / m)``."""
    return float(np.sqrt(T / m))


def hanging_chain_frequencies(L: float, g: float,
                              n: int = 4) -> np.ndarray:
    """Small-oscillation frequencies of a uniform chain hanging from the top.

    The classic solution (Bernoulli) gives modes ``y ~ J0(2 z / sqrt(...))``
    with frequencies set by the zeros ``alpha_k`` of the Bessel function
    ``J0``::

        omega_k = 0.5 * alpha_k * sqrt(g / L).

    Returns the first ``n`` angular frequencies [rad/s].
    """
    alpha = jn_zeros(0, n)
    return 0.5 * alpha * np.sqrt(g / L)


def j0_mode_shape(s: np.ndarray, L: float, alpha_k: float) -> np.ndarray:
    """Hanging-chain mode shape ``J0(alpha_k * sqrt(z / L))``.

    Here ``z`` is the distance measured up from the free bottom end, so for
    arc length ``s`` measured from the top, ``z = L - s``.
    """
    z = L - s
    return j0(alpha_k * np.sqrt(np.clip(z, 0.0, None) / L))
