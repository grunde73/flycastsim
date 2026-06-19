"""Data-driven tackle components for the multi-subdomain fly-casting engine.

A :class:`Component` describes one physical part of the tackle (a rod, a fly
line or a leader) by **tabulated material profiles** sampled at control points
along its local arc-length ``s in [0, length]``:

* ``m``   -- mass per unit length [kg/m]
* ``EI``  -- bending stiffness [N m^2]
* ``d``   -- outer diameter [m] (used by the air-drag law)
* ``eta`` -- material relaxation time [s] (Kelvin-Voigt damping; one scalar)

Components are stored as **JSON metadata + CSV profile tables** and assembled
into a :class:`~flycastsim.fem.multidomain.MultiDomain` by a small ``rig.json``
file that lists the components in order and the junction kinds between them.

The example rig ships **inside the package** at
``flycastsim/data/components/cast1/`` so it is importable from an installed
wheel via :mod:`importlib.resources`.  Users can point the loader at their own
``rig.json`` on disk, or copy the bundled example with :func:`copy_example_rig`.
"""

from __future__ import annotations

import csv
import json
import shutil
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import numpy as np

from .domain import Subdomain
from . import _cast1_data

#: Package sub-path holding the bundled component rigs.
_DATA_PACKAGE = "flycastsim.data.components"


# ---------------------------------------------------------------------------
# Component
# ---------------------------------------------------------------------------
@dataclass
class Component:
    """A single tackle component with tabulated material profiles.

    Args:
        name: Human-readable component name.
        kind: Component kind (``"rod"``, ``"line"``, ``"leader"``, ...).
        length: Total length [m].
        n_nodes: Default number of grid nodes when discretised (>= 3).
        s: Control-point arc-lengths [m], strictly increasing, ``s[0] == 0`` and
            ``s[-1] == length``.
        m: Mass per unit length at each control point [kg/m] (already in
            absolute units; AFTM scaling is applied at load time).
        EI: Bending stiffness at each control point [N m^2].
        d: Outer diameter at each control point [m].
        eta: Material relaxation time [s] (single scalar for the component).
        interp: Interpolation kind (only ``"linear"`` is supported).
    """

    name: str
    kind: str
    length: float
    n_nodes: int
    s: np.ndarray
    m: np.ndarray
    EI: np.ndarray
    d: np.ndarray
    eta: float = 0.0
    interp: str = "linear"

    def __post_init__(self) -> None:
        self.s = np.asarray(self.s, dtype=float)
        self.m = np.asarray(self.m, dtype=float)
        self.EI = np.asarray(self.EI, dtype=float)
        self.d = np.asarray(self.d, dtype=float)
        n = self.s.size
        if n < 2:
            raise ValueError(f"component {self.name!r} needs >= 2 control points")
        if np.any(np.diff(self.s) <= 0):
            raise ValueError(f"component {self.name!r}: s must be increasing")
        for name, arr in (("m", self.m), ("EI", self.EI), ("d", self.d)):
            if arr.shape != (n,):
                raise ValueError(
                    f"component {self.name!r}: {name} has shape {arr.shape}, "
                    f"expected ({n},)")
        if self.interp != "linear":
            raise ValueError(f"unsupported interp {self.interp!r} (use 'linear')")

    def _sample(self, s_grid: np.ndarray) -> tuple[np.ndarray, ...]:
        """Linearly interpolate the profiles onto ``s_grid`` (local coords)."""
        m = np.interp(s_grid, self.s, self.m)
        EI = np.interp(s_grid, self.s, self.EI)
        d = np.interp(s_grid, self.s, self.d)
        return m, EI, d

    def to_subdomain(self, n_nodes: int | None = None, *,
                     s0: float = 0.0) -> Subdomain:
        """Discretise the component onto a uniform grid as a :class:`Subdomain`.

        Args:
            n_nodes: Number of grid nodes; defaults to the component's
                :attr:`n_nodes`.
            s0: Global arc-length offset of the first node [m].

        Returns:
            A :class:`~flycastsim.fem.domain.Subdomain` with the interpolated
            profiles, its ``s`` grid shifted by ``s0``.
        """
        n = int(self.n_nodes if n_nodes is None else n_nodes)
        s_local = np.linspace(0.0, self.length, n)
        m, EI, d = self._sample(s_local)
        eta = np.full(n, float(self.eta))
        return Subdomain(s=s0 + s_local, m=m, EI=EI, d=d, eta=eta)


# ---------------------------------------------------------------------------
# CSV / JSON loading
# ---------------------------------------------------------------------------
def _read_csv_columns(csv_path: Path) -> dict[str, np.ndarray]:
    """Read a CSV with a header row into ``{column_name: float array}``."""
    with open(csv_path, newline="") as fh:
        reader = csv.reader(fh)
        rows = [r for r in reader if r and not r[0].lstrip().startswith("#")]
    if len(rows) < 2:
        raise ValueError(f"{csv_path}: need a header row and >= 1 data row")
    header = [h.strip() for h in rows[0]]
    data = np.array([[float(v) for v in r] for r in rows[1:]], dtype=float)
    return {name: data[:, j] for j, name in enumerate(header)}


def _aftm_mass_scale(shape: np.ndarray, s: np.ndarray, weight: float,
                     head_length: float) -> float:
    """Scale factor turning a relative ``shape`` into kg/m via the AFTM standard.

    The factor is chosen so the mass of the first ``head_length`` metres equals
    the AFTM standard head mass for ``weight``.
    """
    head_mass = _cast1_data.line_head_mass_grams(weight) * 1.0e-3   # kg
    s_end = min(float(head_length), float(s[-1]))
    s_head = np.linspace(s[0], s_end, 256)
    shape_head = np.interp(s_head, s, shape)
    shape_integral = float(np.trapezoid(shape_head, s_head))
    if shape_integral <= 0.0:
        raise ValueError("AFTM mass shape integrates to <= 0")
    return head_mass / shape_integral


def load_component(json_path: str | Path, *,
                   aftm_weight: float | None = None,
                   eta: float | None = None) -> Component:
    """Load a :class:`Component` from its JSON metadata + CSV profile table.

    Args:
        json_path: Path to the component JSON file. The CSV referenced by
            ``profile_csv`` is resolved relative to the JSON file's directory.
        aftm_weight: Override the AFTM line weight used to scale a
            ``mass_mode == "scaled_by_aftm"`` component. Ignored for
            ``"absolute"`` components.
        eta: Override the component's material relaxation time [s].

    Returns:
        A fully populated :class:`Component` (mass already in kg/m).
    """
    json_path = Path(json_path)
    meta = json.loads(json_path.read_text())

    columns = meta["columns"]
    csv_path = json_path.parent / meta["profile_csv"]
    cols = _read_csv_columns(csv_path)

    def col(key: str, default: float | None = None) -> np.ndarray:
        name = columns.get(key)
        if name is None or name not in cols:
            if default is None:
                raise ValueError(f"{csv_path}: missing column for {key!r}")
            return np.full_like(cols[columns["s"]], float(default))
        return cols[name]

    s = col("s")
    EI = col("EI")
    d = col("d", default=0.0)
    m_raw = col("m")

    length = float(meta["length_m"])
    if not np.isclose(s[0], 0.0):
        raise ValueError(f"{csv_path}: first s must be 0, got {s[0]}")
    if not np.isclose(s[-1], length):
        raise ValueError(
            f"{csv_path}: last s ({s[-1]}) must equal length_m ({length})")

    mass_mode = meta.get("mass_mode", "absolute")
    if mass_mode == "absolute":
        m = m_raw
    elif mass_mode == "scaled_by_aftm":
        weight = (aftm_weight if aftm_weight is not None
                  else meta.get("aftm_weight"))
        if weight is None:
            raise ValueError(
                f"{json_path}: mass_mode 'scaled_by_aftm' needs 'aftm_weight'")
        head_len = float(meta.get("aftm_head_length_m",
                                  _cast1_data.AFTM_HEAD_LENGTH_M))
        m = m_raw * _aftm_mass_scale(m_raw, s, weight, head_len)
    else:
        raise ValueError(f"{json_path}: unknown mass_mode {mass_mode!r}")

    eta_val = float(meta.get("eta_s", 0.0)) if eta is None else float(eta)

    return Component(
        name=meta.get("name", json_path.stem),
        kind=meta.get("kind", json_path.stem),
        length=length,
        n_nodes=int(meta["n_nodes"]),
        s=s, m=m, EI=EI, d=d,
        eta=eta_val,
        interp=meta.get("interp", "linear"),
    )


# ---------------------------------------------------------------------------
# Rig (assembly) loading
# ---------------------------------------------------------------------------
def bundled_rig_path(name: str = "cast1") -> Path:
    """Return the filesystem path to a bundled example rig's ``rig.json``.

    Args:
        name: Bundled rig directory name (default ``"cast1"``).

    Returns:
        Path to ``flycastsim/data/components/<name>/rig.json``.
    """
    base = resources.files(_DATA_PACKAGE) / name / "rig.json"
    return Path(str(base))


def copy_example_rig(dest: str | Path, name: str = "cast1") -> Path:
    """Copy a bundled example rig folder to ``dest`` for the user to edit.

    Args:
        dest: Destination directory (created if missing).
        name: Bundled rig directory name (default ``"cast1"``).

    Returns:
        Path to the copied ``rig.json``.
    """
    src_dir = Path(str(resources.files(_DATA_PACKAGE) / name))
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for item in src_dir.iterdir():
        shutil.copy2(item, dest / item.name)
    return dest / "rig.json"


def _resolve_rig(rig_source: str | Path) -> Path:
    """Resolve a rig source (filesystem path or bundled name) to a ``rig.json``."""
    p = Path(rig_source)
    if p.suffix == ".json" and p.exists():
        return p
    if p.is_dir() and (p / "rig.json").exists():
        return p / "rig.json"
    if p.exists():
        return p
    # Fall back to a bundled rig name.
    bundled = bundled_rig_path(str(rig_source))
    if bundled.exists():
        return bundled
    raise FileNotFoundError(f"could not resolve rig source {rig_source!r}")


def load_rig(rig_source: str | Path = "cast1", *,
             aftm_weight: float | None = None,
             eta_overrides: dict[str, float] | None = None,
             n_nodes_overrides: dict[str, int] | None = None):
    """Load a :class:`~flycastsim.fem.multidomain.MultiDomain` from a rig file.

    Args:
        rig_source: Either a filesystem path to a ``rig.json`` (or its directory),
            or a bundled rig name such as ``"cast1"``. Component CSVs are resolved
            relative to the JSON files' directory.
        aftm_weight: Override the AFTM line weight for any
            ``mass_mode == "scaled_by_aftm"`` component (the ``line_weight`` knob).
        eta_overrides: Optional ``{component_kind: eta}`` material-damping
            overrides applied at load time.
        n_nodes_overrides: Optional ``{component_kind: n_nodes}`` grid overrides.

    Returns:
        A :class:`~flycastsim.fem.multidomain.MultiDomain` assembling the
        components in order, joined by the declared junctions.
    """
    from .multidomain import Junction, MultiDomain

    rig_path = _resolve_rig(rig_source)
    rig = json.loads(rig_path.read_text())
    rig_dir = rig_path.parent
    eta_overrides = eta_overrides or {}
    n_nodes_overrides = n_nodes_overrides or {}

    components: list[Component] = []
    for comp_file in rig["components"]:
        comp = load_component(rig_dir / comp_file, aftm_weight=aftm_weight,
                              eta=eta_overrides.get(_peek_kind(rig_dir / comp_file)))
        if comp.kind in n_nodes_overrides:
            comp.n_nodes = int(n_nodes_overrides[comp.kind])
        components.append(comp)

    # Map component kind -> index for resolving junction endpoints by name.
    kind_to_index = {c.kind: i for i, c in enumerate(components)}

    def _endpoint(name) -> int:
        if name in kind_to_index:
            return kind_to_index[name]
        return _index_or_int(name, components)

    junctions: list[Junction] = []
    for j in rig.get("junctions", []):
        a_name, b_name = j["between"]
        junctions.append(Junction(kind=j["kind"],
                                   left=_endpoint(a_name),
                                   right=_endpoint(b_name)))

    return MultiDomain.from_components(components, junctions,
                                       name=rig.get("name", rig_path.stem))


def _peek_kind(json_path: Path) -> str:
    """Read just the ``kind`` field of a component JSON (for eta overrides)."""
    try:
        return json.loads(Path(json_path).read_text()).get("kind", "")
    except Exception:
        return ""


def _index_or_int(name, components: list[Component]) -> int:
    """Resolve a junction endpoint name to a component index."""
    try:
        return int(name)
    except (TypeError, ValueError):
        raise ValueError(f"unknown junction endpoint {name!r}")
