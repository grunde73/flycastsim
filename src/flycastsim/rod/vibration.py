"""Natural bending frequencies of a clamped fly rod with a tip mass.

This is the forward model for the tip-mass frequency test used, together with
the static bend tests, to estimate a rod's stiffness and mass profiles (see
``docs/rod_profile.rst``): the rod is clamped at :math:`s_c` (measured from
the butt), a point mass :math:`m_t` is attached at the tip, and the lowest
bending frequency is measured for a series of tip masses.

The rod is modelled as a linear Euler--Bernoulli beam with variable bending
stiffness :math:`EI(s)` and linear mass density :math:`\\mu(s)`,

.. math::

    \\left(EI\\, w''\\right)'' - \\omega^2 \\mu\\, w = 0,

clamped at :math:`s_c` (:math:`w = w' = 0`) and free at the tip apart from the
point mass (:math:`EI\\,w'' = 0`, :math:`(EI\\,w'')' = -m_t\\,\\omega^2 w`).  It is
discretised with cubic Hermite beam elements (displacement and slope per node),
giving the generalised eigenproblem :math:`K v = \\omega^2 M v`, solved for its
lowest modes as :math:`M v = \\omega^{-2} K v` (diagonally scaled) with
:func:`scipy.linalg.eigh`.  Element integrals use 4-point Gauss--Legendre
quadrature, so a linear :math:`\\mu` within an element is integrated exactly;
pass ``breakpoints`` (e.g. ferrule positions) to put nodes where the profiles
have jumps.  Eigenvalues converge as :math:`O(h^4)`; the default 60 elements
give ~1e-9 relative accuracy, while very fine meshes (hundreds of elements)
lose accuracy to round-off because :math:`K` scales as :math:`EI/h^3`.

Deliberate simplifications: small vibrations about the *straight* rod (the
static sag under gravity and the gravity pre-stress are neglected), no rotary
inertia or shear deformation (slender rod), and a rigid clamp.  SI units
throughout; frequencies are returned in Hz.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from scipy.linalg import eigh

from .elastica import Profile, _as_function

# 4-point Gauss--Legendre rule mapped to [0, 1].
_GAUSS_X, _GAUSS_W = np.polynomial.legendre.leggauss(4)
_GAUSS_X = 0.5 * (_GAUSS_X + 1.0)
_GAUSS_W = 0.5 * _GAUSS_W


def _hermite(xi: np.ndarray, h: float) -> tuple[np.ndarray, np.ndarray]:
    """Cubic Hermite shape functions and their second ``s``-derivatives.

    Returns arrays of shape ``(4, len(xi))`` for the element DOFs
    ``[w_0, w'_0, w_1, w'_1]``.
    """
    N = np.array([1 - 3 * xi**2 + 2 * xi**3,
                  h * (xi - 2 * xi**2 + xi**3),
                  3 * xi**2 - 2 * xi**3,
                  h * (-xi**2 + xi**3)])
    B = np.array([(-6 + 12 * xi) / h**2,
                  (-4 + 6 * xi) / h,
                  (6 - 12 * xi) / h**2,
                  (-2 + 6 * xi) / h])
    return N, B


def beam_mesh(length: float, s_clamp: float = 0.0, n_elements: int = 60,
              breakpoints: Sequence[float] = ()) -> np.ndarray:
    """Uniform node positions on ``[s_clamp, length]`` plus ``breakpoints``.

    Breakpoints inside the interval are inserted as extra nodes so profile
    jumps (ferrules) fall on element boundaries.
    """
    nodes = np.linspace(s_clamp, length, n_elements + 1)
    extra = [b for b in breakpoints if s_clamp < b < length]
    nodes = np.union1d(nodes, extra)
    # drop nodes that nearly coincide with a breakpoint
    keep = np.concatenate([[True], np.diff(nodes) > 1e-9 * (length - s_clamp)])
    return nodes[keep]


def assemble(EI: Profile, mu: Profile, nodes: np.ndarray
             ) -> tuple[np.ndarray, np.ndarray]:
    """Global stiffness and mass matrices of the clamped beam.

    The clamped DOFs at ``nodes[0]`` are removed, so the DOF vector is
    ``[w_1, w'_1, ..., w_n, w'_n]`` and the tip displacement is DOF ``-2``.

    Args:
        EI: Bending stiffness [N m^2], constant or vectorised ``f(s)``.
        mu: Linear mass density [kg/m], constant or vectorised ``f(s)``.
        nodes: Node positions, clamp first and tip last [m].
    """
    EI_f, mu_f = _as_function(EI), _as_function(mu)
    n_dof = 2 * len(nodes)
    K = np.zeros((n_dof, n_dof))
    M = np.zeros((n_dof, n_dof))
    for e, (a, b) in enumerate(zip(nodes[:-1], nodes[1:])):
        h = b - a
        s = a + h * _GAUSS_X
        N, B = _hermite(_GAUSS_X, h)
        wk = h * _GAUSS_W * EI_f(s)
        wm = h * _GAUSS_W * mu_f(s)
        idx = slice(2 * e, 2 * e + 4)
        K[idx, idx] += (B * wk) @ B.T
        M[idx, idx] += (N * wm) @ N.T
    return K[2:, 2:], M[2:, 2:]


def _frequencies(K, M, tip_mass, n_modes):
    if tip_mass:
        M = M.copy()
        M[-2, -2] += tip_mass
    # Solve the inverse problem M v = (1 / omega^2) K v for its largest
    # eigenvalues: K is positive definite (clamped), and the lowest modes are
    # then well conditioned even on fine meshes, where K ~ EI / h^3.
    # Symmetric diagonal scaling balances displacement and slope DOFs.
    d = 1.0 / np.sqrt(np.diag(K))
    K = K * np.outer(d, d)
    M = M * np.outer(d, d)
    n = K.shape[0]
    inv_omega2 = eigh(M, K, eigvals_only=True,
                      subset_by_index=[n - n_modes, n - 1])[::-1]
    return 1.0 / (2 * np.pi * np.sqrt(inv_omega2))


def natural_frequencies(EI: Profile, mu: Profile, *, length: float,
                        s_clamp: float = 0.0, tip_mass: float = 0.0,
                        n_modes: int = 1, n_elements: int = 60,
                        breakpoints: Sequence[float] = ()) -> np.ndarray:
    """Lowest bending frequencies [Hz] of the clamped rod with a tip mass.

    Args:
        EI: Bending stiffness [N m^2], constant or vectorised ``f(s)``.
        mu: Linear mass density [kg/m], constant or vectorised ``f(s)``.
        length: Rod length; the tip is at ``s = length`` [m].
        s_clamp: Clamp position measured from the butt [m].
        tip_mass: Point mass at the tip [kg].
        n_modes: Number of frequencies to return (ascending).
        n_elements: Number of uniform elements before adding breakpoints.
        breakpoints: Positions that must be nodes, e.g. ferrules [m].
    """
    nodes = beam_mesh(length, s_clamp, n_elements, breakpoints)
    K, M = assemble(EI, mu, nodes)
    return _frequencies(K, M, tip_mass, n_modes)


def frequency_vs_tip_mass(EI: Profile, mu: Profile,
                          tip_masses: Sequence[float], *, length: float,
                          s_clamp: float = 0.0, n_elements: int = 60,
                          breakpoints: Sequence[float] = ()) -> np.ndarray:
    """Fundamental frequency [Hz] for each tip mass [kg].

    The beam matrices are assembled once and reused for every tip mass, which
    is what the frequency-test residuals in the profile fit need.
    """
    nodes = beam_mesh(length, s_clamp, n_elements, breakpoints)
    K, M = assemble(EI, mu, nodes)
    return np.array([_frequencies(K, M, m, 1)[0] for m in tip_masses])
