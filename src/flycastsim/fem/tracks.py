"""Casting strokes from points tracked in a video of a cast.

A :class:`StrokeTracks` holds two points tracked on the rod in each video
frame, and :func:`stroke_from_tracks` turns them into a
:class:`~flycastsim.fem.stroke.Stroke` that can drive a cast simulation
(step 4 of the workflow).  The points are tracked in another program; this
module does not read video.  Tracks are stored like strokes, as **JSON
metadata + a CSV table**:

.. code-block:: json

    {
      "name": "My cast",
      "kind": "stroke_tracks",
      "table_csv": "tracks.csv",
      "columns": {"frame": "frame",
                  "butt_x": "butt_x", "butt_y": "butt_y",
                  "rod_x": "rod_x", "rod_y": "rod_y"},
      "fps": 240,
      "units": "px",
      "scale": {"length_m": 2.74, "from_px": [412, 655], "to_px": [1310, 201]},
      "y_axis": "down",
      "casting_direction": "right",
      "rsp": {"frame": 152},
      "butt_offset_m": 0.10,
      "tracking_noise": 1.5
    }

Conventions
-----------
* **Points.**  ``butt`` is a point on the rod at or near the rod butt and
  ``rod`` a point further up the stiff butt section.  Only the direction from
  ``butt`` to ``rod`` is used, so ``rod`` may be a different place on the rod
  in each row.  ``butt_offset_m`` is the distance from the rod butt end to the
  ``butt`` point (default 0).  The ``columns`` mapping may name further points
  as ``<name>_x`` / ``<name>_y`` pairs (e.g. ``tip``); they are kept in
  :attr:`StrokeTracks.extra` and do not affect the stroke.
* **Time.**  The table has a time column ``t`` [s] or a ``frame`` column with
  ``fps``.  ``rsp`` gives the RSP (Rod Straight Position) instant as a
  ``frame`` or a time ``t`` in the table's time base; it becomes ``t = 0`` of
  the stroke.
* **Units and orientation.**  ``units`` is ``"px"`` or ``"m"``.  Pixel tables
  need a ``scale``: ``{"m_per_px": ...}`` or a known length ``length_m``
  between the pixel points ``from_px`` and ``to_px``.  ``y_axis`` says whether
  the table's ``y`` grows ``"down"`` (default for pixels) or ``"up"`` (default
  for metres), and ``casting_direction`` whether the cast goes to the
  ``"right"`` (default) or ``"left"`` in the table's ``x``.
* **Missing points.**  A row with an empty ``butt`` or ``rod`` value is
  skipped, so frames where a point is hidden can be left blank.

Method
------
#. The points are brought into the stroke frame (metres, casting direction
   ``+x``, ``+y`` up).
#. The rod-butt angle of a row is the direction from ``butt`` to ``rod``,
   unwrapped over time so that it is continuous, and within 180 degrees of
   zero at RSP.  The hand position is the rod butt end: the ``butt``
   point moved back by ``butt_offset_m`` along that direction.
#. The angle and the two hand coordinates are each fitted over time with a
   cubic smoothing spline (Reinsch 1967).  With a stated tracking noise
   (standard deviation per coordinate, in table units) the spline is the
   smoothest one whose residual equals the noise (Reinsch's criterion); the
   angle noise of a row is ``sqrt(2) * noise / d`` with ``d`` the distance
   between the two points.  Without a stated noise the smoothing parameter is
   chosen by generalised cross-validation (Craven & Wahba 1979).  This is the
   standard method for differentiating tracked motion data (Woltring 1986).
#. The fitted curves are sampled at a fixed step from the first to the last
   track time, with RSP at ``t = 0`` and the hand at the origin there.

Simplifications: the rod is taken as straight between the two points (its
bend under load biases the angle slightly), the camera is assumed square to
the casting plane, and one smoothing strength is used for the whole track, so
a sharp stop is rounded off somewhat.  :class:`StrokeExtraction` returns the
raw samples and the fit residuals so that this can be judged.

References
----------
* C. H. Reinsch, *Smoothing by spline functions*, Numer. Math. 10 (1967)
  177-183.
* P. Craven and G. Wahba, *Smoothing noisy data with spline functions*,
  Numer. Math. 31 (1979) 377-403.
* H. J. Woltring, *A Fortran package for generalized, cross-validatory spline
  smoothing and differentiation*, Adv. Eng. Software 8 (1986) 104-113.
"""

from __future__ import annotations

import csv
import json
import math
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy.interpolate import PchipInterpolator, make_smoothing_spline
from scipy.optimize import brentq

from .stroke import COARSE_STEP_S, Stroke, _read_table, load_stroke

#: Fewest usable rows a track table may have.
MIN_TRACK_ROWS = 8

#: Fraction of the peak speed above which a track counts as starting or
#: ending in motion.
MOVING_END_FRACTION = 0.20

#: Part of the track's duration, at each end, over which the mean speed is
#: taken for that check.
MOVING_END_WINDOW = 0.05

#: Default time step [s] of an extracted stroke table (that of the bundled
#: Cast #1 stroke).
DEFAULT_STROKE_STEP_S = 0.0025

#: JSON keys that are part of the track format rather than metadata.
_FORMAT_KEYS = ("name", "kind", "table_csv", "columns", "fps", "units",
                "scale", "y_axis", "casting_direction", "rsp",
                "butt_offset_m", "tracking_noise")

#: Column keys every track table maps (besides ``t`` or ``frame``).
_POINT_KEYS = ("butt_x", "butt_y", "rod_x", "rod_y")

#: Search range for the smoothing parameter, as log10 with the time measured
#: in median track steps.
_LOG_LAM_RANGE = (-8.0, 12.0)


def _frozen(values) -> np.ndarray:
    """A read-only float copy of ``values``."""
    arr = np.array(values, dtype=float)
    arr.flags.writeable = False
    return arr


@dataclass(frozen=True, eq=False)
class StrokeTracks:
    """Two points tracked on the rod over time (see the module docstring).

    Raises ``ValueError`` when the arrays do not match in shape, a time or a
    ``butt``/``rod`` value is not finite, there are fewer than
    :data:`MIN_TRACK_ROWS` rows, the times are not strictly increasing, a
    setting has an unknown or invalid value, pixel tracks have no scale, or
    ``meta`` uses a format key.
    """

    #: Display name.
    name: str
    #: Row times [s] in the table's own time base, strictly increasing.
    t: np.ndarray
    #: ``butt`` point positions ``(N, 2)`` in table units.
    butt: np.ndarray
    #: ``rod`` point positions ``(N, 2)`` in table units.
    rod: np.ndarray
    #: Time of RSP [s] in the table's time base.
    rsp_t: float
    #: Table units, ``"px"`` or ``"m"``.
    units: str = "px"
    #: Metres per table unit; required for pixels, 1 for metres.
    m_per_unit: float | None = None
    #: ``"down"`` or ``"up"``; ``None`` picks down for pixels, up for metres.
    y_axis: str | None = None
    #: ``"right"`` or ``"left"``: where the cast goes in the table's ``x``.
    casting_direction: str = "right"
    #: Distance [m] from the rod butt end to the ``butt`` point.
    butt_offset_m: float = 0.0
    #: Tracking noise (standard deviation per coordinate, table units), or
    #: ``None`` when not stated.
    tracking_noise: float | None = None
    #: Capture frame rate [1/s], when known.
    fps: float | None = None
    #: Further tracked points, name -> ``(N, 2)``; may hold NaN where a point
    #: was not tracked.  Not used for the stroke.
    extra: dict = field(default_factory=dict)
    #: Other metadata from the JSON file.
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        t = _frozen(self.t)
        butt = _frozen(self.butt)
        rod = _frozen(self.rod)
        if t.ndim != 1:
            raise ValueError("track times must be 1-D")
        for key, arr in (("butt", butt), ("rod", rod)):
            if arr.shape != (t.size, 2):
                raise ValueError(f"track point {key!r} must have shape (N, 2) "
                                 f"with one row per time")
            if not np.all(np.isfinite(arr)):
                raise ValueError(f"track point {key!r} has a value that is "
                                 f"not finite")
        if not np.all(np.isfinite(t)):
            raise ValueError("track times have a value that is not finite")
        if t.size < MIN_TRACK_ROWS:
            raise ValueError(f"tracks need at least {MIN_TRACK_ROWS} rows, "
                             f"got {t.size}")
        if np.any(np.diff(t) <= 0.0):
            raise ValueError("track times must be strictly increasing")
        if not math.isfinite(self.rsp_t):
            raise ValueError("the RSP time must be finite")
        if self.units not in ("px", "m"):
            raise ValueError(f"units must be 'px' or 'm', got {self.units!r}")
        scale = self.m_per_unit
        if self.units == "m":
            if scale is not None and scale != 1.0:
                raise ValueError("tracks in metres must not give a scale")
            scale = 1.0
        elif scale is None:
            raise ValueError("tracks in pixels need a scale")
        if not (math.isfinite(scale) and scale > 0.0):
            raise ValueError(f"the scale must be positive, got {scale!r}")
        y_axis = self.y_axis
        if y_axis is None:
            y_axis = "down" if self.units == "px" else "up"
        if y_axis not in ("down", "up"):
            raise ValueError(f"y_axis must be 'down' or 'up', got {y_axis!r}")
        if self.casting_direction not in ("right", "left"):
            raise ValueError(f"casting_direction must be 'right' or 'left', "
                             f"got {self.casting_direction!r}")
        if not (math.isfinite(self.butt_offset_m)
                and self.butt_offset_m >= 0.0):
            raise ValueError("butt_offset_m must be zero or positive")
        if self.tracking_noise is not None:
            _check_noise(self.tracking_noise)
        if self.fps is not None and not (math.isfinite(self.fps)
                                         and self.fps > 0.0):
            raise ValueError(f"fps must be positive, got {self.fps!r}")
        extra = {}
        for key, arr in self.extra.items():
            pts = _frozen(arr)
            if pts.shape != (t.size, 2):
                raise ValueError(f"extra point {key!r} must have shape "
                                 f"(N, 2) with one row per time")
            if key in ("butt", "rod"):
                raise ValueError(f"extra point must not be named {key!r}")
            extra[str(key)] = pts
        reserved = sorted(set(self.meta) & set(_FORMAT_KEYS))
        if reserved:
            raise ValueError(f"track metadata must not use the format keys "
                             f"{reserved}")
        for name, value in (("t", t), ("butt", butt), ("rod", rod),
                            ("rsp_t", float(self.rsp_t)),
                            ("m_per_unit", float(scale)), ("y_axis", y_axis),
                            ("butt_offset_m", float(self.butt_offset_m)),
                            ("extra", extra), ("meta", dict(self.meta))):
            object.__setattr__(self, name, value)

    @property
    def median_step(self) -> float:
        """Median time step between rows [s]."""
        return float(np.median(np.diff(self.t)))


def _check_noise(noise) -> float:
    if not (isinstance(noise, (int, float)) and math.isfinite(noise)
            and noise > 0.0):
        raise ValueError(f"the tracking noise must be positive, got {noise!r}")
    return float(noise)


# ---------------------------------------------------------------------------
# Loading and saving
# ---------------------------------------------------------------------------
def _resolve_tracks(source: str | Path) -> Path:
    p = Path(source)
    if p.is_file():
        return p
    if p.is_dir() and (p / "tracks.json").is_file():
        return p / "tracks.json"
    raise FileNotFoundError(f"could not find track files at {source!r}")


def _number(value, what: str) -> float:
    """``value`` as a finite float, or a ``ValueError`` naming ``what``."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{what} must be a number, got {value!r}")  # noqa: TRY004
    if not math.isfinite(value):
        raise ValueError(f"{what} must be finite, got {value!r}")
    return float(value)


def _pixel_point(value, what: str) -> np.ndarray:
    if not (isinstance(value, (list, tuple)) and len(value) == 2):
        raise ValueError(f"{what} must be an [x, y] pair, got {value!r}")
    return np.array([_number(v, what) for v in value])


def _scale_from_spec(spec: dict, json_path: Path) -> float | None:
    """Metres per pixel from the ``scale`` entry (``None`` for metres)."""
    scale = spec.get("scale")
    if spec["units"] == "m":
        if scale is not None:
            raise ValueError(f"{json_path}: tracks in metres must not give "
                             f"a 'scale'")
        return None
    if not isinstance(scale, dict):
        raise ValueError(f"{json_path}: tracks in pixels need a 'scale' "  # noqa: TRY004
                         f"mapping")
    if "m_per_px" in scale:
        value = _number(scale["m_per_px"], f"{json_path}: scale.m_per_px")
    else:
        for key in ("length_m", "from_px", "to_px"):
            if key not in scale:
                raise ValueError(f"{json_path}: 'scale' must give 'm_per_px' "
                                 f"or 'length_m', 'from_px' and 'to_px'")
        length = _number(scale["length_m"], f"{json_path}: scale.length_m")
        a = _pixel_point(scale["from_px"], f"{json_path}: scale.from_px")
        b = _pixel_point(scale["to_px"], f"{json_path}: scale.to_px")
        dist = float(np.hypot(*(b - a)))
        if dist <= 0.0:
            raise ValueError(f"{json_path}: the scale points coincide")
        value = length / dist
    if value <= 0.0:
        raise ValueError(f"{json_path}: the scale must be positive")
    return value


def _floats(cols: dict, name: str, csv_path: Path, keep: np.ndarray | None = None,
            blank_ok: bool = False) -> np.ndarray:
    """Column ``name`` as floats; blank cells become NaN when allowed."""
    if name not in cols:
        raise ValueError(f"{csv_path}: missing column {name!r}")
    raws = cols[name]
    if keep is not None:
        raws = [raw for raw, kept in zip(raws, keep, strict=True) if kept]
    out = np.empty(len(raws))
    for i, raw in enumerate(raws):
        text = raw.strip()
        if not text:
            if blank_ok:
                out[i] = np.nan
                continue
            raise ValueError(f"{csv_path}: column {name!r} has an empty value")
        try:
            out[i] = float(text)
        except ValueError as exc:
            raise ValueError(f"{csv_path}: column {name!r}: {exc}") from exc
        if not math.isfinite(out[i]) and not blank_ok:
            raise ValueError(f"{csv_path}: column {name!r} has a value that "
                             f"is not finite")
    return out


def load_tracks(source: str | Path | StrokeTracks) -> StrokeTracks:
    """Load tracks from track files.

    Args:
        source: A path to a ``tracks.json``, a folder holding one, or a
            :class:`StrokeTracks` (returned as is).

    Returns:
        The loaded :class:`StrokeTracks`.

    Raises:
        FileNotFoundError: The source or its table does not exist.
        ValueError: The files do not follow the track file format.
    """
    if isinstance(source, StrokeTracks):
        return source
    json_path = _resolve_tracks(source)
    try:
        spec = json.loads(json_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"{json_path}: invalid JSON: {exc}") from exc
    if not isinstance(spec, dict) or spec.get("kind") != "stroke_tracks":
        raise ValueError(f"{json_path}: 'kind' must be 'stroke_tracks'")
    for key in ("name", "table_csv", "columns", "units", "rsp"):
        if key not in spec:
            raise ValueError(f"{json_path}: missing key {key!r}")
    if spec["units"] not in ("px", "m"):
        raise ValueError(f"{json_path}: 'units' must be 'px' or 'm', got "
                         f"{spec['units']!r}")
    columns = spec["columns"]
    if not isinstance(columns, dict):
        raise ValueError(f"{json_path}: 'columns' must be a mapping")  # noqa: TRY004
    for key, name in columns.items():
        if not isinstance(name, str):
            raise ValueError(f"{json_path}: column name for {key!r} must be "  # noqa: TRY004
                             f"a string, got {name!r}")
    if ("t" in columns) == ("frame" in columns):
        raise ValueError(f"{json_path}: 'columns' must name exactly one of "
                         f"'t' and 'frame'")
    for key in _POINT_KEYS:
        if key not in columns:
            raise ValueError(f"{json_path}: 'columns' must name {key!r}")
    extra_names = []
    for key in columns:
        if key in ("t", "frame") or key in _POINT_KEYS:
            continue
        if not key.endswith(("_x", "_y")) or len(key) < 3:
            raise ValueError(f"{json_path}: unknown column key {key!r}")
        point = key[:-2]
        if f"{point}_x" not in columns or f"{point}_y" not in columns:
            raise ValueError(f"{json_path}: extra point {point!r} needs both "
                             f"'{point}_x' and '{point}_y'")
        if point not in extra_names:
            extra_names.append(point)
    if not isinstance(spec["table_csv"], str):
        raise ValueError(f"{json_path}: 'table_csv' must be a string")  # noqa: TRY004

    fps = None
    if "fps" in spec:
        fps = _number(spec["fps"], f"{json_path}: 'fps'")
        if fps <= 0.0:
            raise ValueError(f"{json_path}: 'fps' must be positive")
    if "frame" in columns and fps is None:
        raise ValueError(f"{json_path}: a table indexed by frame needs 'fps'")

    rsp = spec["rsp"]
    if not isinstance(rsp, dict) or ("t" in rsp) == ("frame" in rsp):
        raise ValueError(f"{json_path}: 'rsp' must give exactly one of 't' "
                         f"and 'frame'")
    if "frame" in rsp:
        if fps is None:
            raise ValueError(f"{json_path}: an RSP frame needs 'fps'")
        rsp_t = _number(rsp["frame"], f"{json_path}: rsp.frame") / fps
    else:
        rsp_t = _number(rsp["t"], f"{json_path}: rsp.t")

    m_per_px = _scale_from_spec(spec, json_path)

    csv_path = json_path.parent / spec["table_csv"]
    if not csv_path.is_file():
        raise FileNotFoundError(f"{csv_path}: track table not found")
    cols = _read_table(csv_path)
    for key in _POINT_KEYS:
        if columns[key] not in cols:
            raise ValueError(f"{csv_path}: missing column {columns[key]!r}")
    n_rows = len(cols[columns["butt_x"]])
    keep = np.ones(n_rows, dtype=bool)
    for key in _POINT_KEYS:
        keep &= np.array([bool(v.strip()) for v in cols[columns[key]]],
                         dtype=bool)
    if "frame" in columns:
        t = _floats(cols, columns["frame"], csv_path, keep) / fps
    else:
        t = _floats(cols, columns["t"], csv_path, keep)
    butt = np.column_stack([_floats(cols, columns[k], csv_path, keep)
                            for k in ("butt_x", "butt_y")])
    rod = np.column_stack([_floats(cols, columns[k], csv_path, keep)
                           for k in ("rod_x", "rod_y")])
    extra = {
        point: np.column_stack([
            _floats(cols, columns[f"{point}_{ax}"], csv_path, keep,
                    blank_ok=True) for ax in ("x", "y")])
        for point in extra_names}
    noise = spec.get("tracking_noise")
    if noise is not None:
        try:
            _check_noise(noise)
        except ValueError as exc:
            raise ValueError(f"{json_path}: {exc}") from exc
    meta = {k: v for k, v in spec.items() if k not in _FORMAT_KEYS}
    try:
        return StrokeTracks(
            name=str(spec["name"]), t=t, butt=butt, rod=rod, rsp_t=rsp_t,
            units=spec["units"], m_per_unit=m_per_px,
            y_axis=spec.get("y_axis"),
            casting_direction=spec.get("casting_direction", "right"),
            butt_offset_m=_number(spec.get("butt_offset_m", 0.0),
                                  "'butt_offset_m'"),
            tracking_noise=noise, fps=fps, extra=extra, meta=meta)
    except ValueError as exc:
        raise ValueError(f"{json_path}: {exc}") from exc


def _fmt(v: float) -> str:
    """Shortest round-trip text for a float; empty for NaN."""
    return "" if math.isnan(v) else repr(float(v))


def save_tracks(tracks: StrokeTracks, dest: str | Path) -> Path:
    """Write ``tracks`` to the folder ``dest`` as ``tracks.json`` + ``tracks.csv``.

    The table is written with a time column, and the values so that
    :func:`load_tracks` gives them back exactly.

    Args:
        tracks: The tracks to write.
        dest: Destination folder (created if missing).

    Returns:
        Path to the written ``tracks.json``.
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    columns = {"t": "t_s"} | {k: k for k in _POINT_KEYS}
    data = [tracks.t, tracks.butt[:, 0], tracks.butt[:, 1],
            tracks.rod[:, 0], tracks.rod[:, 1]]
    for point, pts in tracks.extra.items():
        columns |= {f"{point}_x": f"{point}_x", f"{point}_y": f"{point}_y"}
        data += [pts[:, 0], pts[:, 1]]
    csv_path = dest / "tracks.csv"
    with open(csv_path, "w", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(list(columns.values()))
        for row in zip(*data, strict=True):
            writer.writerow([_fmt(v) for v in row])
    spec = {"name": tracks.name, "kind": "stroke_tracks",
            "table_csv": csv_path.name, "columns": columns}
    if tracks.fps is not None:
        spec["fps"] = tracks.fps
    spec["units"] = tracks.units
    if tracks.units == "px":
        spec["scale"] = {"m_per_px": tracks.m_per_unit}
    spec |= {"y_axis": tracks.y_axis,
             "casting_direction": tracks.casting_direction,
             "rsp": {"t": tracks.rsp_t},
             "butt_offset_m": tracks.butt_offset_m}
    if tracks.tracking_noise is not None:
        spec["tracking_noise"] = tracks.tracking_noise
    spec |= tracks.meta
    json_path = dest / "tracks.json"
    json_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")
    return json_path


# ---------------------------------------------------------------------------
# Tracks -> stroke
# ---------------------------------------------------------------------------
@dataclass(frozen=True, eq=False)
class StrokeExtraction:
    """Result of :func:`stroke_from_tracks`.

    The raw samples are what the tracked points give before smoothing, in the
    stroke's frame and units, one entry per track row.  Compare them with the
    stroke to judge whether the smoothing has flattened it.
    """

    #: The extracted stroke.
    stroke: Stroke
    #: Raw sample times [s] relative to RSP.
    t: np.ndarray
    #: Raw rod-butt angle [deg] at each sample.
    angle_deg: np.ndarray
    #: Raw hand ``x`` position [m], zero at RSP.
    hand_x: np.ndarray
    #: Raw hand ``y`` position [m], zero at RSP.
    hand_y: np.ndarray
    #: RMS deviation of the stroke's angle from the raw samples [deg].
    rms_angle_deg: float
    #: RMS deviation of the stroke's hand path from the raw samples [m], per
    #: coordinate: ``sqrt(mean((dx**2 + dy**2) / 2))``.
    rms_hand_m: float


class _Curve:
    """A function of time with a derivative, ``curve(t, nu)``."""

    def __init__(self, spline, t0: float, step: float):
        self._spline, self._t0, self._step = spline, t0, step

    def __call__(self, t, nu: int = 0) -> np.ndarray:
        u = (np.asarray(t, dtype=float) - self._t0) / self._step
        return self._spline(u, nu) / self._step ** nu


def _smooth(t: np.ndarray, y: np.ndarray, sigma: np.ndarray | None,
            weights: np.ndarray | None = None) -> _Curve:
    """Cubic smoothing spline through ``y(t)``.

    With ``sigma`` (the noise of each sample) the smoothing parameter is the
    largest one for which the mean of ``(residual / sigma)**2`` is 1
    (Reinsch's criterion).  Without it the parameter is chosen by generalised
    cross-validation, with the relative ``weights`` if given.
    """
    step = float(np.median(np.diff(t)))
    u = (t - t[0]) / step           # sample spacing ~1: a well-scaled search
    if sigma is None:
        return _Curve(make_smoothing_spline(u, y, w=weights), t[0], step)
    w = 1.0 / sigma ** 2

    def excess(log_lam: float) -> float:
        spline = make_smoothing_spline(u, y, w=w, lam=10.0 ** log_lam)
        return float(np.mean(w * (y - spline(u)) ** 2)) - 1.0

    lo, hi = _LOG_LAM_RANGE
    if excess(hi) <= 0.0:           # smoother than the stated noise
        log_lam = hi
    elif excess(lo) >= 0.0:         # cannot get closer: interpolate
        log_lam = lo
    else:
        log_lam = brentq(excess, lo, hi, xtol=1e-4)
    return _Curve(make_smoothing_spline(u, y, w=w, lam=10.0 ** log_lam),
                  t[0], step)


def _raw_curve(t: np.ndarray, y: np.ndarray) -> PchipInterpolator:
    return PchipInterpolator(t, y)


def stroke_from_tracks(tracks: StrokeTracks | str | Path, *,
                       noise: float | None = None, smoothing: bool = True,
                       dt: float = DEFAULT_STROKE_STEP_S,
                       name: str | None = None) -> StrokeExtraction:
    """Turn tracked points into a casting stroke (see the module docstring).

    Args:
        tracks: The tracks, or a path to track files.
        noise: Tracking noise, the standard deviation per coordinate in the
            units of the table.  Defaults to the tracks' ``tracking_noise``;
            when neither is given the smoothing strength is chosen from the
            data by generalised cross-validation.
        smoothing: ``False`` switches smoothing off; the stroke table then
            holds the raw samples at the track's own times.
        dt: Time step [s] of the stroke table when smoothing is on.
        name: Name of the stroke (default: the name of the tracks).

    Returns:
        A :class:`StrokeExtraction` with the stroke, the raw samples and the
        RMS deviations.

    Raises:
        ValueError: RSP lies outside the track, the two points coincide in a
            row, or ``noise`` or ``dt`` is not positive.

    Warns:
        UserWarning: The median track step exceeds
            :data:`~flycastsim.fem.stroke.COARSE_STEP_S`, or the rod or the
            hand moves faster than :data:`MOVING_END_FRACTION` of its peak
            speed over the first or last :data:`MOVING_END_WINDOW` of the
            track.
    """
    tracks = load_tracks(tracks)
    if noise is None:
        noise = tracks.tracking_noise
    if noise is not None:
        noise = _check_noise(noise)
    if not (math.isfinite(dt) and dt > 0.0):
        raise ValueError(f"dt must be positive, got {dt!r}")

    # 1. Stroke frame: metres, casting direction +x, +y up.
    flip = np.array([1.0 if tracks.casting_direction == "right" else -1.0,
                     -1.0 if tracks.y_axis == "down" else 1.0])
    scale = tracks.m_per_unit
    butt = tracks.butt * flip * scale
    rod = tracks.rod * flip * scale
    t = tracks.t - tracks.rsp_t
    if not (t[0] <= 0.0 <= t[-1]):
        raise ValueError(
            f"RSP (t = {tracks.rsp_t:g} s in the table) lies outside the "
            f"track, which runs from {tracks.t[0]:g} s to {tracks.t[-1]:g} s")

    # 2. Angle and rod butt end of each row.
    d = rod - butt
    dist = np.hypot(d[:, 0], d[:, 1])
    if np.any(dist <= 0.0):
        row = int(np.argmin(dist))
        raise ValueError(f"the butt and rod points coincide in row {row} of "
                         f"the track (t = {tracks.t[row]:g} s)")
    angle = np.unwrap(np.arctan2(d[:, 1], d[:, 0]))
    # Whole turns are arbitrary: put the angle at RSP in [-180, 180] deg.
    angle -= 2.0 * np.pi * np.round(np.interp(0.0, t, angle) / (2.0 * np.pi))
    hand = butt - tracks.butt_offset_m * d / dist[:, None]

    # 3. Curves through the samples.
    if smoothing:
        if noise is None:
            method = "smoothing spline, generalised cross-validation"
            w = dist ** 2 / np.mean(dist ** 2)
            f_angle = _smooth(t, angle, None, w)
            f_x = _smooth(t, hand[:, 0], None)
            f_y = _smooth(t, hand[:, 1], None)
        else:
            method = "smoothing spline, Reinsch criterion"
            sigma_m = noise * scale
            f_angle = _smooth(t, angle, math.sqrt(2.0) * sigma_m / dist)
            sigma_h = np.full(t.size, sigma_m)
            f_x = _smooth(t, hand[:, 0], sigma_h)
            f_y = _smooth(t, hand[:, 1], sigma_h)
        # 4. Fixed-step table inside the track, with t = 0 on the grid.
        k = np.arange(math.ceil(t[0] / dt - 1e-9),
                      math.floor(t[-1] / dt + 1e-9) + 1)
        table_t = k * dt
        if table_t.size < 2:
            raise ValueError(f"the track is too short for a stroke table "
                             f"with a {dt:g} s step")
    else:
        method = "none"
        f_angle = _raw_curve(t, angle)
        f_x = _raw_curve(t, hand[:, 0])
        f_y = _raw_curve(t, hand[:, 1])
        table_t = t
    origin = np.array([float(f_x(0.0)), float(f_y(0.0))])
    raw_x, raw_y = hand[:, 0] - origin[0], hand[:, 1] - origin[1]
    if smoothing:
        table = (f_angle(table_t), f_x(table_t) - origin[0],
                 f_y(table_t) - origin[1])
    else:
        table = (angle, raw_x, raw_y)       # the raw samples, exactly

    _warn_about_track(tracks, t, f_angle, f_x, f_y, table_t)

    stroke = Stroke(
        name=tracks.name if name is None else name, t=table_t,
        angle_deg=np.rad2deg(table[0]), hand_x=table[1], hand_y=table[2])
    rms_angle = rms_hand = 0.0
    if smoothing:
        sx, sy = stroke.hand_xy(t)
        rms_angle = float(np.sqrt(np.mean(
            (np.rad2deg(stroke.angle(t) - angle)) ** 2)))
        rms_hand = float(np.sqrt(np.mean(((sx - raw_x) ** 2
                                          + (sy - raw_y) ** 2) / 2.0)))
    source = {
        "method": "tracks", "tracks": tracks.name, "samples": int(t.size),
        "median_step_s": tracks.median_step, "smoothing": method,
        "tracking_noise": ("automatic" if smoothing and noise is None
                           else noise),
        "tracking_noise_units": tracks.units,
        "rms_angle_deg": rms_angle, "rms_hand_m": rms_hand,
        "m_per_unit": scale, "butt_offset_m": tracks.butt_offset_m}
    if tracks.fps is not None:
        source["capture_fps"] = tracks.fps
    if "source" in tracks.meta:
        source["tracks_source"] = tracks.meta["source"]
    stroke = Stroke(name=stroke.name, t=stroke.t, angle_deg=stroke.angle_deg,
                    hand_x=stroke.hand_x, hand_y=stroke.hand_y,
                    meta={"description": f"Extracted from the tracks "
                                         f"{tracks.name!r}.",
                          "source": source})
    return StrokeExtraction(
        stroke=stroke, t=_frozen(t), angle_deg=_frozen(np.rad2deg(angle)),
        hand_x=_frozen(raw_x), hand_y=_frozen(raw_y),
        rms_angle_deg=rms_angle, rms_hand_m=rms_hand)


def _warn_about_track(tracks, t, f_angle, f_x, f_y, table_t) -> None:
    """The coarse-track and moving-ends warnings."""
    step = tracks.median_step
    if step > COARSE_STEP_S + 1e-12:
        warnings.warn(
            f"tracks {tracks.name!r} are coarsely sampled (median step "
            f"{step * 1e3:.1f} ms > {COARSE_STEP_S * 1e3:.0f} ms, about "
            f"{1.0 / step:.0f} frames per second); the stop of the stroke "
            f"may not be resolved at that frame rate",
            UserWarning, stacklevel=3)
    # Mean speed over a short window at each end: the end derivative of a
    # fitted curve is too noisy to judge by.
    window = max(MOVING_END_WINDOW * (t[-1] - t[0]), 3.0 * step)
    times = np.union1d(t, table_t)
    peak = {"angle": float(np.abs(f_angle(times, 1)).max()),
            "hand": float(np.hypot(f_x(times, 1), f_y(times, 1)).max())}
    for label, t_a, t_b in (("starts", t[0], min(t[0] + window, t[-1])),
                            ("ends", max(t[-1] - window, t[0]), t[-1])):
        span = t_b - t_a
        speed = {"angle": abs(float(f_angle(t_b) - f_angle(t_a))) / span,
                 "hand": float(np.hypot(f_x(t_b) - f_x(t_a),
                                        f_y(t_b) - f_y(t_a))) / span}
        moving = [what for what in ("angle", "hand")
                  if speed[what] > MOVING_END_FRACTION * peak[what] > 0.0]
        if moving:
            warnings.warn(
                f"tracks {tracks.name!r}: the track {label} while the "
                f"{' and the '.join(moving)} still "
                f"{'move' if len(moving) > 1 else 'moves'} fast (more than "
                f"{MOVING_END_FRACTION:.0%} of the peak speed); the "
                f"simulation starts from rest and holds the stroke's end "
                f"values, so include the pause before the stroke and the "
                f"follow-through after the stop",
                UserWarning, stacklevel=3)


# ---------------------------------------------------------------------------
# Synthetic tracks
# ---------------------------------------------------------------------------
def tracks_from_stroke(stroke: Stroke | str | Path, *, fps: float = 240.0,
                       m_per_px: float = 0.003, units: str = "px",
                       y_axis: str | None = None,
                       casting_direction: str = "right",
                       rod_point_m: float = 0.40, butt_offset_m: float = 0.0,
                       pause_s: float = 0.0, noise: float = 0.0,
                       seed: int | None = None,
                       origin: tuple[float, float] = (0.0, 0.0),
                       name: str | None = None) -> StrokeTracks:
    """Make the tracks a camera would give of a known stroke.

    The rod is taken as straight between the two points: the ``butt`` point
    lies ``butt_offset_m`` from the hand along the stroke's rod-butt angle and
    the ``rod`` point ``rod_point_m`` further along the same line.  The points
    are sampled every ``1 / fps``, from ``pause_s`` before the stroke's first
    time to ``pause_s`` after its last; in the pauses the stroke holds its
    end values.  Without
    noise, :func:`stroke_from_tracks` with smoothing off gives back the
    stroke's angle and its hand path relative to RSP.

    Args:
        stroke: The stroke, or a stroke source for
            :func:`~flycastsim.fem.stroke.load_stroke`.
        fps: Frame rate [1/s].
        m_per_px: Metres per pixel (used when ``units`` is ``"px"``).
        units: ``"px"`` or ``"m"``.
        y_axis: ``"down"`` or ``"up"`` (default: down for pixels, up for
            metres).
        casting_direction: ``"right"`` or ``"left"``.
        rod_point_m: Distance [m] from the ``butt`` point to the ``rod``
            point.
        butt_offset_m: Distance [m] from the rod butt end to the ``butt``
            point.
        pause_s: Time [s] filmed before and after the stroke, with the rod
            and the hand held still.
        noise: Standard deviation of the Gaussian tracking noise added to
            each coordinate, in table units.
        seed: Seed of the noise generator.
        origin: Table position of the stroke's origin, in table units.
        name: Name of the tracks (default: derived from the stroke's name).

    Returns:
        The :class:`StrokeTracks`, with ``tracking_noise`` set to ``noise``
        when it is positive.
    """
    stroke = load_stroke(stroke)
    if not (math.isfinite(fps) and fps > 0.0):
        raise ValueError(f"fps must be positive, got {fps!r}")
    if not (math.isfinite(rod_point_m) and rod_point_m > 0.0):
        raise ValueError("rod_point_m must be positive")
    if not (math.isfinite(noise) and noise >= 0.0):
        raise ValueError("noise must be zero or positive")
    if not (math.isfinite(pause_s) and pause_s >= 0.0):
        raise ValueError("pause_s must be zero or positive")
    t0, t1 = stroke.t_span
    t0, t1 = t0 - pause_s, t1 + pause_s
    table_t = np.arange(math.floor((t1 - t0) * fps + 1e-9) + 1) / fps
    t = t0 + table_t
    a = stroke.angle(t)
    along = np.column_stack([np.cos(a), np.sin(a)])
    hx, hy = stroke.hand_xy(t)
    butt = np.column_stack([hx, hy]) + butt_offset_m * along
    rod = butt + rod_point_m * along
    scale = m_per_px if units == "px" else 1.0
    if y_axis is None:
        y_axis = "down" if units == "px" else "up"
    flip = np.array([1.0 if casting_direction == "right" else -1.0,
                     -1.0 if y_axis == "down" else 1.0])
    butt = butt * flip / scale + np.asarray(origin, dtype=float)
    rod = rod * flip / scale + np.asarray(origin, dtype=float)
    if noise > 0.0:
        rng = np.random.default_rng(seed)
        butt = butt + rng.normal(0.0, noise, butt.shape)
        rod = rod + rng.normal(0.0, noise, rod.shape)
    return StrokeTracks(
        name=f"{stroke.name} (synthetic tracks)" if name is None else name,
        t=table_t, butt=butt, rod=rod, rsp_t=-t0, units=units,
        m_per_unit=m_per_px if units == "px" else None, y_axis=y_axis,
        casting_direction=casting_direction, butt_offset_m=butt_offset_m,
        tracking_noise=noise if noise > 0.0 else None, fps=float(fps),
        meta={"source": {"method": "synthetic", "stroke": stroke.name,
                         "rod_point_m": rod_point_m, "pause_s": pause_s,
                         "noise": noise, "seed": seed}})
