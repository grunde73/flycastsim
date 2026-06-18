"""Tackle / subdomain description for the FEM fly-casting engine.

A :class:`Subdomain` describes one continuous beam/line segment by its
material properties as functions of the Lagrangian arc-length coordinate
``s``.  The properties follow the notation of Ekander, Perkins & Richards
(*Sports Engineering* 2025):

* ``m``   -- mass per unit length ``m(s)`` [kg/m]
* ``d``   -- outer diameter ``d(s)`` [m]
* ``EI``  -- bending stiffness ``EI(s)`` [N m^2]
* ``eta`` -- material relaxation time ``eta(s)`` [s] (Kelvin-Voigt damping)

The core engine works on a single subdomain.  Multi-subdomain coupling
(rod + fly line + leader) is a planned extension and is intentionally kept
out of this class for now.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Subdomain:
    """A single continuous beam/line segment discretised on an ``s``-grid.

    Args:
        s: 1-D array of node arc-length coordinates [m], strictly increasing.
        m: Mass per unit length at each node [kg/m].
        EI: Bending stiffness at each node [N m^2].
        d: Outer diameter at each node [m]. Defaults to zeros (unused by the
            core engine, required once air drag is added).
        eta: Material relaxation time at each node [s]. Defaults to zeros
            (purely elastic core engine).
    """

    s: np.ndarray
    m: np.ndarray
    EI: np.ndarray
    d: np.ndarray | None = None
    eta: np.ndarray | None = None

    def __post_init__(self) -> None:
        self.s = np.asarray(self.s, dtype=float)
        n = self.s.size
        if n < 3:
            raise ValueError("A subdomain needs at least 3 nodes")
        if np.any(np.diff(self.s) <= 0):
            raise ValueError("s must be strictly increasing")

        self.m = self._as_field(self.m, n, "m")
        self.EI = self._as_field(self.EI, n, "EI")
        self.d = self._as_field(0.0 if self.d is None else self.d, n, "d")
        self.eta = self._as_field(0.0 if self.eta is None else self.eta,
                                  n, "eta")

    @staticmethod
    def _as_field(value, n: int, name: str) -> np.ndarray:
        arr = np.asarray(value, dtype=float)
        if arr.ndim == 0:
            arr = np.full(n, float(arr))
        if arr.shape != (n,):
            raise ValueError(
                f"{name} must be scalar or have shape ({n},), got {arr.shape}")
        return arr

    @property
    def n_nodes(self) -> int:
        return self.s.size

    @property
    def length(self) -> float:
        return float(self.s[-1] - self.s[0])

    @property
    def uniform(self) -> bool:
        """True if the grid spacing is (numerically) uniform."""
        ds = np.diff(self.s)
        return bool(np.allclose(ds, ds[0]))

    @property
    def ds(self) -> float:
        """Uniform grid spacing. Raises if the grid is non-uniform."""
        if not self.uniform:
            raise ValueError("ds is only defined for a uniform grid")
        return float(self.s[1] - self.s[0])

    def dEI_ds(self) -> np.ndarray:
        """Centered finite-difference of ``EI(s)`` w.r.t. ``s``."""
        return np.gradient(self.EI, self.s)


def uniform_beam(length: float, n_nodes: int, *, m: float, EI: float,
                 d: float = 0.0, eta: float = 0.0,
                 s0: float = 0.0) -> Subdomain:
    """Build a uniform beam/line subdomain.

    Args:
        length: Total length [m].
        n_nodes: Number of grid nodes (>= 3).
        m: Mass per unit length [kg/m].
        EI: Bending stiffness [N m^2].
        d: Outer diameter [m].
        eta: Material relaxation time [s].
        s0: Arc-length of the first node [m].

    Returns:
        A :class:`Subdomain` with uniform properties.
    """
    s = np.linspace(s0, s0 + length, n_nodes)
    return Subdomain(s=s,
                     m=np.full(n_nodes, float(m)),
                     EI=np.full(n_nodes, float(EI)),
                     d=np.full(n_nodes, float(d)),
                     eta=np.full(n_nodes, float(eta)))


def chain(length: float, n_nodes: int, *, m: float,
          EI: float = 0.0, s0: float = 0.0) -> Subdomain:
    """Build a (near) bending-free chain/cable subdomain.

    A chain is the ``EI -> 0`` limit of a beam.  A tiny non-zero ``EI`` may
    be supplied for numerical regularisation.

    Args:
        length: Total length [m].
        n_nodes: Number of grid nodes (>= 3).
        m: Mass per unit length [kg/m].
        EI: (Small) bending stiffness [N m^2], default 0.
        s0: Arc-length of the first node [m].
    """
    return uniform_beam(length, n_nodes, m=m, EI=EI, s0=s0)
