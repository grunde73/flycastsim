"""Solution-vector packing/unpacking for the FEM fly-casting engine.

The engine solves for seven coupled fields along the ``s``-grid, following
Ekander, Perkins & Richards (*Sports Engineering* 2025):

==========  =======================================  =====
index       field                                    symbol
==========  =======================================  =====
0           tangential velocity                      ``u_s``
1           normal velocity                          ``u_n``
2           tangential (tension) force               ``F_s``
3           normal (shear) force                     ``F_n``
4           tangent angle                            ``phi``
5           curvature ``= d(phi)/ds``                ``nu_z``
6           curvature gradient ``= d(nu_z)/ds``      ``Gamma_z``
==========  =======================================  =====

The flat solution vector ``X`` uses a **node-major (interleaved)** layout::

    X = [f0@n0, f1@n0, ..., f6@n0, f0@n1, ..., f6@n1, ...]

so that field ``f`` at node ``i`` is stored at ``X[i * NFIELDS + f]``.  This
keeps the Jacobian banded with a small bandwidth because centered spatial
differences only couple neighbouring nodes ``i-1, i, i+1``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Field indices --------------------------------------------------------------
U_S = 0
U_N = 1
F_S = 2
F_N = 3
PHI = 4
NU_Z = 5
GAMMA_Z = 6

NFIELDS = 7

FIELD_NAMES = ("u_s", "u_n", "F_s", "F_n", "phi", "nu_z", "Gamma_z")


def n_unknowns(n_nodes: int) -> int:
    """Length of the flat solution vector for ``n_nodes`` grid nodes."""
    return n_nodes * NFIELDS


def idx(node: int, field: int) -> int:
    """Flat-vector index of ``field`` at ``node`` (node-major layout)."""
    return node * NFIELDS + field


@dataclass
class Fields:
    """A convenient view of the seven fields on the grid.

    Each attribute is a 1-D array of length ``n_nodes``.
    """

    u_s: np.ndarray
    u_n: np.ndarray
    F_s: np.ndarray
    F_n: np.ndarray
    phi: np.ndarray
    nu_z: np.ndarray
    Gamma_z: np.ndarray

    @property
    def n_nodes(self) -> int:
        return self.u_s.size

    def to_vector(self) -> np.ndarray:
        """Pack the fields into the flat node-major solution vector."""
        stacked = np.stack(
            (self.u_s, self.u_n, self.F_s, self.F_n,
             self.phi, self.nu_z, self.Gamma_z),
            axis=1,
        )
        return stacked.reshape(-1)

    @classmethod
    def from_vector(cls, x: np.ndarray) -> "Fields":
        """Unpack a flat node-major solution vector into :class:`Fields`."""
        x = np.asarray(x, dtype=float)
        if x.size % NFIELDS != 0:
            raise ValueError(
                f"vector length {x.size} is not a multiple of {NFIELDS}")
        grid = x.reshape(-1, NFIELDS)
        return cls(
            u_s=grid[:, U_S].copy(),
            u_n=grid[:, U_N].copy(),
            F_s=grid[:, F_S].copy(),
            F_n=grid[:, F_N].copy(),
            phi=grid[:, PHI].copy(),
            nu_z=grid[:, NU_Z].copy(),
            Gamma_z=grid[:, GAMMA_Z].copy(),
        )

    def copy(self) -> "Fields":
        return Fields(
            self.u_s.copy(), self.u_n.copy(), self.F_s.copy(),
            self.F_n.copy(), self.phi.copy(), self.nu_z.copy(),
            self.Gamma_z.copy(),
        )


def zeros(n_nodes: int) -> Fields:
    """Return a :class:`Fields` of zeros for ``n_nodes`` nodes."""
    z = np.zeros(n_nodes)
    return Fields(z.copy(), z.copy(), z.copy(), z.copy(),
                  z.copy(), z.copy(), z.copy())
