"""Casting strokes as data: rod-butt angle and hand position over time.

A :class:`Stroke` is the caster's motion that drives a cast simulation (step 4
of the workflow).  It is a **sampled table** of time, rod-butt angle and,
optionally, hand position, stored like the tackle components as **JSON
metadata + a CSV table**:

.. code-block:: json

    {
      "name": "Cast #1 stroke",
      "kind": "stroke",
      "table_csv": "stroke.csv",
      "columns": {"t": "t_s", "angle": "angle_deg",
                  "x": "hand_x_m", "y": "hand_y_m"},
      "description": "...",
      "source": {"...": "..."}
    }

Conventions
-----------
* **Time** ``t`` [s] is relative to RSP (Rod Straight Position), so RSP is
  ``t = 0``.  Times must be strictly increasing.
* **Angle** [deg] is the absolute tangent angle of the rod at the handle, with
  the casting direction as ``+x``: 0 deg is level forward, 90 deg straight up.
* **Hand position** ``x``, ``y`` [m] is the rod butt in the same frame, ``+y``
  up.  The two columns are given together or not at all; without them the
  hand stays fixed at the origin.

Evaluation
----------
Between samples the angle and the hand position are interpolated with a
shape-preserving PCHIP spline (:class:`scipy.interpolate.PchipInterpolator`),
which passes through every sample, never overshoots and has a continuous
first derivative, so the prescribed handle velocity is continuous.  Outside
the table the end values are held and the hand velocity is zero.  The hand
velocity is the derivative of the interpolated hand position.

The simulated cast is sensitive to how a coarse stroke is interpolated, so
:func:`load_stroke` warns when the largest time step exceeds
:data:`COARSE_STEP_S`.

Bundled strokes live in ``flycastsim/data/strokes/<name>/`` and load by name,
e.g. ``load_stroke("cast1")``.
"""

from __future__ import annotations

import csv
import json
import math
import warnings
from dataclasses import dataclass, field
from functools import cached_property
from importlib import resources
from pathlib import Path

import numpy as np
from scipy.interpolate import PchipInterpolator

#: Package sub-path holding the bundled strokes.
_DATA_PACKAGE = "flycastsim.data.strokes"

#: Largest time step [s] in a loaded stroke table before a warning is given.
COARSE_STEP_S = 0.010

#: Default column names written by :func:`save_stroke`.
DEFAULT_COLUMNS = {"t": "t_s", "angle": "angle_deg",
                   "x": "hand_x_m", "y": "hand_y_m"}

#: JSON keys that are part of the format rather than metadata.
_FORMAT_KEYS = ("name", "kind", "table_csv", "columns")


@dataclass(frozen=True, eq=False)
class Stroke:
    """A casting stroke sampled over time (see the module docstring).

    Raises ``ValueError`` when the columns differ in length, a value is not
    finite, there are fewer than two samples, the times are not strictly
    increasing, or only one of ``hand_x`` and ``hand_y`` is given.
    """

    #: Display name.
    name: str
    #: Sample times [s] relative to RSP, strictly increasing.
    t: np.ndarray
    #: Rod-butt tangent angle [deg] at each sample.
    angle_deg: np.ndarray
    #: Hand ``x`` position [m] at each sample, or ``None`` for a fixed hand.
    hand_x: np.ndarray | None = None
    #: Hand ``y`` position [m] at each sample, or ``None`` for a fixed hand.
    hand_y: np.ndarray | None = None
    #: Other metadata from the JSON file (e.g. ``description``, ``source``).
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        t = np.asarray(self.t, dtype=float)
        angle = np.asarray(self.angle_deg, dtype=float)
        if (self.hand_x is None) != (self.hand_y is None):
            raise ValueError("hand_x and hand_y must be given together")
        arrays = {"t": t, "angle": angle}
        if self.hand_x is not None:
            arrays["x"] = np.asarray(self.hand_x, dtype=float)
            arrays["y"] = np.asarray(self.hand_y, dtype=float)
        for key, arr in arrays.items():
            if arr.ndim != 1 or arr.shape != t.shape:
                raise ValueError(f"stroke column {key!r} must be 1-D with "
                                 f"the same length as t")
            if not np.all(np.isfinite(arr)):
                raise ValueError(f"stroke column {key!r} has a value that "
                                 f"is not finite")
        if t.size < 2:
            raise ValueError("a stroke needs at least two samples")
        if np.any(np.diff(t) <= 0.0):
            raise ValueError("stroke times must be strictly increasing")
        object.__setattr__(self, "t", t)
        object.__setattr__(self, "angle_deg", angle)
        if self.hand_x is not None:
            object.__setattr__(self, "hand_x", arrays["x"])
            object.__setattr__(self, "hand_y", arrays["y"])
        object.__setattr__(self, "meta", dict(self.meta))

    # -- interpolants (built once; the BC is evaluated every Newton step) ---
    @cached_property
    def _angle_spline(self) -> PchipInterpolator:
        return PchipInterpolator(self.t, self.angle_deg)

    @cached_property
    def _hand_splines(self) -> tuple[PchipInterpolator, PchipInterpolator] | None:
        if self.hand_x is None:
            return None
        return (PchipInterpolator(self.t, self.hand_x),
                PchipInterpolator(self.t, self.hand_y))

    def _clip(self, t) -> np.ndarray:
        return np.clip(np.asarray(t, dtype=float), self.t[0], self.t[-1])

    @property
    def t_span(self) -> tuple[float, float]:
        """``(first, last)`` sample time [s]."""
        return float(self.t[0]), float(self.t[-1])

    @property
    def has_hand_path(self) -> bool:
        """Whether the stroke includes a hand path."""
        return self.hand_x is not None

    def angle(self, t) -> np.ndarray:
        """Rod-butt tangent angle [rad] at times ``t`` [s]."""
        return np.deg2rad(self._angle_spline(self._clip(t)))

    def hand_xy(self, t) -> tuple[np.ndarray, np.ndarray]:
        """Hand position ``(x, y)`` [m] at times ``t`` [s]."""
        tc = self._clip(t)
        if self._hand_splines is None:
            return np.zeros_like(tc), np.zeros_like(tc)
        sx, sy = self._hand_splines
        return sx(tc), sy(tc)

    def hand_vel(self, t) -> tuple[np.ndarray, np.ndarray]:
        """Hand velocity ``(vx, vy)`` [m/s] at times ``t`` [s].

        The derivative of :meth:`hand_xy`; zero outside the sampled range.
        """
        t = np.asarray(t, dtype=float)
        tc = self._clip(t)
        if self._hand_splines is None:
            return np.zeros_like(tc), np.zeros_like(tc)
        inside = (t >= self.t[0]) & (t <= self.t[-1])
        sx, sy = self._hand_splines
        return (np.where(inside, sx(tc, 1), 0.0),
                np.where(inside, sy(tc, 1), 0.0))


# ---------------------------------------------------------------------------
# Loading and saving
# ---------------------------------------------------------------------------
def bundled_stroke_path(name: str = "cast1") -> Path:
    """Return the path to a bundled stroke's ``stroke.json``.

    Args:
        name: Bundled stroke folder name (default ``"cast1"``).

    Returns:
        Path to ``flycastsim/data/strokes/<name>/stroke.json``.
    """
    base = resources.files(_DATA_PACKAGE) / name / "stroke.json"
    return Path(str(base))


def _resolve_stroke(source: str | Path) -> Path:
    """Resolve a stroke source (path or bundled name) to a ``stroke.json``."""
    p = Path(source)
    if p.is_file():
        return p
    if p.is_dir() and (p / "stroke.json").is_file():
        return p / "stroke.json"
    try:
        bundled = bundled_stroke_path(str(source))
    except ModuleNotFoundError:       # no bundled strokes installed
        bundled = None
    if bundled is not None and bundled.is_file():
        return bundled
    raise FileNotFoundError(f"could not resolve stroke source {source!r}")


def _read_table(csv_path: Path) -> dict[str, list[str]]:
    """Read a CSV with a header row into ``{column_name: [raw values]}``."""
    with open(csv_path, newline="") as fh:
        rows = [r for r in csv.reader(fh)
                if r and not r[0].lstrip().startswith("#")]
    if not rows:
        raise ValueError(f"{csv_path}: empty stroke table")
    header = [h.strip() for h in rows[0]]
    cols: dict[str, list[str]] = {h: [] for h in header}
    for r in rows[1:]:
        if len(r) != len(header):
            raise ValueError(f"{csv_path}: row {r!r} does not match the header")
        for h, v in zip(header, r, strict=True):
            cols[h].append(v)
    return cols


def _column(cols: dict, name: str, csv_path: Path) -> np.ndarray:
    if name not in cols:
        raise ValueError(f"{csv_path}: missing column {name!r}")
    try:
        return np.array([float(v) for v in cols[name]], dtype=float)
    except ValueError as exc:
        raise ValueError(f"{csv_path}: column {name!r}: {exc}") from exc


def load_stroke(source: str | Path | Stroke = "cast1") -> Stroke:
    """Load a stroke from stroke files.

    Args:
        source: A path to a ``stroke.json``, a folder holding one, a bundled
            stroke name such as ``"cast1"``, or a :class:`Stroke` (returned
            as is).

    Returns:
        The loaded :class:`Stroke`.

    Raises:
        FileNotFoundError: The source is neither a path nor a bundled name.
        ValueError: The files do not follow the stroke file format.

    Warns:
        UserWarning: The largest time step exceeds :data:`COARSE_STEP_S`.
    """
    if isinstance(source, Stroke):
        return source
    json_path = _resolve_stroke(source)
    try:
        spec = json.loads(json_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"{json_path}: invalid JSON: {exc}") from exc
    if not isinstance(spec, dict) or spec.get("kind") != "stroke":
        raise ValueError(f"{json_path}: 'kind' must be 'stroke'")
    for key in ("name", "table_csv", "columns"):
        if key not in spec:
            raise ValueError(f"{json_path}: missing key {key!r}")
    columns = spec["columns"]
    if not isinstance(columns, dict):
        # A malformed file is a ValueError by the cast-stroke spec.
        raise ValueError(f"{json_path}: 'columns' must be a mapping")  # noqa: TRY004
    for key in ("t", "angle"):
        if key not in columns:
            raise ValueError(f"{json_path}: 'columns' must name {key!r}")
    if ("x" in columns) != ("y" in columns):
        raise ValueError(f"{json_path}: hand columns 'x' and 'y' must be "
                         f"given together")

    csv_path = json_path.parent / spec["table_csv"]
    if not csv_path.is_file():
        raise FileNotFoundError(f"{csv_path}: stroke table not found")
    cols = _read_table(csv_path)
    t = _column(cols, columns["t"], csv_path)
    angle = _column(cols, columns["angle"], csv_path)
    hand_x = hand_y = None
    if "x" in columns:
        hand_x = _column(cols, columns["x"], csv_path)
        hand_y = _column(cols, columns["y"], csv_path)
    meta = {k: v for k, v in spec.items() if k not in _FORMAT_KEYS}
    try:
        stroke = Stroke(name=str(spec["name"]), t=t, angle_deg=angle,
                        hand_x=hand_x, hand_y=hand_y, meta=meta)
    except ValueError as exc:
        raise ValueError(f"{csv_path}: {exc}") from exc

    step = float(np.max(np.diff(stroke.t)))
    if step > COARSE_STEP_S + 1e-12:
        warnings.warn(
            f"stroke {stroke.name!r} is coarsely sampled (largest time step "
            f"{step * 1e3:.1f} ms > {COARSE_STEP_S * 1e3:.0f} ms); the "
            f"simulated cast depends strongly on how it is interpolated",
            UserWarning, stacklevel=2)
    return stroke


def _fmt(v: float) -> str:
    """Shortest round-trip text for a float (``repr`` of a Python float)."""
    return repr(float(v)) if math.isfinite(v) else str(v)


def save_stroke(stroke: Stroke, dest: str | Path) -> Path:
    """Write ``stroke`` to the folder ``dest`` as ``stroke.json`` + ``stroke.csv``.

    The values are written so that :func:`load_stroke` gives them back
    exactly.

    Args:
        stroke: The stroke to write.
        dest: Destination folder (created if missing).

    Returns:
        Path to the written ``stroke.json``.
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    columns = {"t": DEFAULT_COLUMNS["t"], "angle": DEFAULT_COLUMNS["angle"]}
    data = [stroke.t, stroke.angle_deg]
    if stroke.has_hand_path:
        columns |= {"x": DEFAULT_COLUMNS["x"], "y": DEFAULT_COLUMNS["y"]}
        data += [stroke.hand_x, stroke.hand_y]
    csv_path = dest / "stroke.csv"
    with open(csv_path, "w", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(list(columns.values()))
        for row in zip(*data, strict=True):
            writer.writerow([_fmt(v) for v in row])
    spec = {"name": stroke.name, "kind": "stroke", "table_csv": csv_path.name,
            "columns": columns, **stroke.meta}
    json_path = dest / "stroke.json"
    json_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")
    return json_path
