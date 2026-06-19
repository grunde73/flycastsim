"""Multi-subdomain assembly for the FEM fly-casting engine.

The core engine (:mod:`flycastsim.fem.operators`, :mod:`flycastsim.fem.solver`)
solves a single :class:`~flycastsim.fem.domain.Subdomain`.  Real tackle is a
chain of physically distinct parts -- a rod, a fly line and a leader -- each with
its own material profile, joined at junctions.  :class:`MultiDomain` holds that
ordered chain of subdomains together with the :class:`Junction` coupling between
consecutive parts, and provides the global-indexing helpers the multi-subdomain
solver needs.

Global degree-of-freedom layout
-------------------------------
The subdomains are concatenated into one global, node-major solution vector::

    [ subdomain 0 nodes | subdomain 1 nodes | ... ]

so the global index of local node ``j`` in subdomain ``i`` is
``node_offsets[i] + j`` and field ``f`` there lives at
``(node_offsets[i] + j) * NFIELDS + f`` -- exactly the single-subdomain layout of
:mod:`flycastsim.fem.state`, just over more nodes.

Each junction connects the **last** node of its left subdomain to the **first**
node of its right subdomain with six coupling equations (see
:mod:`flycastsim.fem.operators`).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .domain import Subdomain

JUNCTION_KINDS = ("pinned", "welded")


@dataclass
class Junction:
    """A coupling between two consecutive subdomains.

    Connects the last node of subdomain ``left`` to the first node of subdomain
    ``right``.

    Args:
        kind: ``"pinned"`` (free hinge: no bending moment transmitted) or
            ``"welded"`` (continuous: tangent angle and bending moment
            transmitted).
        left: Index of the left subdomain.
        right: Index of the right subdomain.
    """

    kind: str
    left: int
    right: int

    def __post_init__(self) -> None:
        if self.kind not in JUNCTION_KINDS:
            raise ValueError(
                f"junction kind {self.kind!r} not in {JUNCTION_KINDS}")


@dataclass
class MultiDomain:
    """An ordered chain of subdomains joined by junctions.

    Args:
        subdomains: The component subdomains, in order along the arc length.
        junctions: The couplings between consecutive subdomains.
        name: Optional human-readable name.
    """

    subdomains: list[Subdomain]
    junctions: list[Junction] = field(default_factory=list)
    name: str = ""

    def __post_init__(self) -> None:
        if len(self.subdomains) < 1:
            raise ValueError("a MultiDomain needs at least one subdomain")
        counts = [sd.n_nodes for sd in self.subdomains]
        self._offsets = np.concatenate(([0], np.cumsum(counts)))[:-1].astype(int)
        for j in self.junctions:
            if not (0 <= j.left < self.n_subdomains
                    and 0 <= j.right < self.n_subdomains):
                raise ValueError(f"junction {j} references unknown subdomain")

    # -- construction -------------------------------------------------------
    @classmethod
    def from_components(cls, components, junctions: list[Junction],
                        *, name: str = "") -> "MultiDomain":
        """Build from :class:`~flycastsim.fem.components.Component` objects.

        Each component is discretised on its own ``n_nodes`` grid and offset by
        the cumulative length of the preceding components, so the global ``s``
        grid is continuous across junctions.
        """
        subdomains: list[Subdomain] = []
        s0 = 0.0
        for comp in components:
            subdomains.append(comp.to_subdomain(s0=s0))
            s0 += comp.length
        return cls(subdomains=subdomains, junctions=list(junctions), name=name)

    # -- sizes / indexing ---------------------------------------------------
    @property
    def n_subdomains(self) -> int:
        return len(self.subdomains)

    @property
    def node_offsets(self) -> np.ndarray:
        """Global index of the first node of each subdomain."""
        return self._offsets

    @property
    def n_nodes(self) -> int:
        """Total number of global nodes."""
        return int(sum(sd.n_nodes for sd in self.subdomains))

    @property
    def s(self) -> np.ndarray:
        """Concatenated global arc-length grid [m]."""
        return np.concatenate([sd.s for sd in self.subdomains])

    def subdomain_slice(self, i: int) -> slice:
        """Global node-index slice of subdomain ``i``."""
        start = int(self._offsets[i])
        return slice(start, start + self.subdomains[i].n_nodes)

    def junction_nodes(self, j: Junction) -> tuple[int, int]:
        """Global node indices ``(left_last, right_first)`` joined by ``j``."""
        left_last = int(self._offsets[j.left]) + self.subdomains[j.left].n_nodes - 1
        right_first = int(self._offsets[j.right])
        return left_last, right_first

    def end_nodes(self) -> tuple[int, int]:
        """Global node indices of the two physical ends (handle, tip)."""
        first = 0
        last = self.n_nodes - 1
        return first, last
