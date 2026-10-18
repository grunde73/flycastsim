"""Load rod measurement data sets (``rod.yaml``) for the profile fit.

Each measured rod has a folder with a ``rod.yaml`` (schema
``flycastsim.rod.measurement/1``) describing the rod, the clamp, the image
calibration and the test data (static bend image sequence, CCS, tip-mass
frequency test); see ``docs/rod_profile.rst``.  Paths in the file are
relative to its folder.  Unknown values are ``null``.

:func:`load_rod_measurement` reads the file into a :class:`RodMeasurement`,
which builds the inputs of :mod:`flycastsim.rod.profile_fit`:
:meth:`~RodMeasurement.mass_model`, :meth:`~RodMeasurement.frequency_data`,
:meth:`~RodMeasurement.ccs_data`, :meth:`~RodMeasurement.image_transform`
and, via :mod:`flycastsim.rod.imaging`, the bend frames
(:meth:`~RodMeasurement.extract_bend_frames`).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .imaging import extract_centerline, load_gray
from .profile_fit import (BendFrame, CCSData, FrequencyData, ImageTransform,
                          MonotoneLogEI, ProfileFitProblem, ProfileFitResult,
                          SectionMassModel, fit_profile)
from .swingweight import RodSection

SCHEMA = "flycastsim.rod.measurement/1"

#: Fit settings for :func:`fit_rod`.  ``"full"`` is what the bundled rods
#: were fitted with; ``"quick"`` uses fewer frames, points and coefficients
#: and looser tolerances (roughly 3-5x faster, slightly less accurate).
FIT_PRESETS: dict[str, dict] = {
    "quick": {"every": 3, "n_points": 20, "n_coef": 7,
              "xtol": 1e-8, "ftol": 1e-8},
    "full": {"every": 2, "n_points": 30, "n_coef": 8,
             "xtol": 1e-10, "ftol": 1e-10},
}


def _get(d: dict | None, key: str, default=None):
    if d is None:
        return default
    value = d.get(key, default)
    return default if value is None else value


@dataclass
class RodMeasurement:
    """A rod's measurement data set, as read from ``rod.yaml``.

    Attributes:
        root: Folder of the ``rod.yaml``; relative paths resolve from here.
        id: Short identifier (e.g. ``"PA905"``).
        label: Make and model.
        length: Assembled rod length [m].
        sections: Measured sections (butt to tip), or ``None``.
        ferrule_overlap: Overlap per joint [m], or ``None``.
        clamp_s: Clamp position from the butt [m].
        clamp_angle: Clamp angle above the horizontal [rad].
        raw: The parsed YAML, for fields without a dedicated attribute.
    """

    root: Path
    id: str
    label: str
    length: float
    sections: list[RodSection] | None
    ferrule_overlap: float | None
    clamp_s: float
    clamp_angle: float
    raw: dict = field(repr=False)

    @property
    def free_length(self) -> float:
        """Clamp-to-tip length [m]."""
        return self.length - self.clamp_s

    # -- mass ---------------------------------------------------------------
    def mass_model(self, n_sections: int = 3, has_reel_seat: bool = True,
                   **kwargs) -> SectionMassModel:
        """Section mass model with the measured sections as priors.

        Without section data a *guess* for a finished single-handed rod of
        ``n_sections`` equal sections is used (about 60/25/15 % of a 90 g
        rod for three sections, balance points at 0.45 of the section, the
        butt's lower because of the grip) with wide priors (±50 % mass,
        ±5 cm balance point), so the bend and frequency data dominate.
        """
        if self.sections:
            overlap = self.ferrule_overlap
            if overlap is None:
                n = max(len(self.sections) - 1, 1)
                overlap = (sum(s.length for s in self.sections)
                           - self.length) / n
            return SectionMassModel(
                lengths=[s.length for s in self.sections],
                ferrule_overlap=overlap,
                masses=[s.mass for s in self.sections],
                mass_centers=[s.mass_center for s in self.sections],
                has_reel_seat=has_reel_seat, **kwargs)
        overlap = self.ferrule_overlap if self.ferrule_overlap else 0.06
        l_sec = (self.length + (n_sections - 1) * overlap) / n_sections
        share = np.geomspace(4.0, 1.0, n_sections)
        masses = 0.090 * share / share.sum()
        centers = np.full(n_sections, 0.45 * l_sec)
        centers[0] = 0.25 * l_sec if has_reel_seat else centers[0]
        kwargs.setdefault("mass_sigma", None)
        kwargs.setdefault("mass_center_sigma", 0.05)
        model = SectionMassModel(lengths=[l_sec] * n_sections,
                                 ferrule_overlap=overlap,
                                 masses=list(masses),
                                 mass_centers=list(centers),
                                 has_reel_seat=has_reel_seat, **kwargs)
        return model

    # -- test data ------------------------------------------------------------
    def frequency_data(self, sigma: float = 0.01) -> FrequencyData | None:
        """Tip-mass frequency test (CSV columns ``m[g]``, ``f[hz]``)."""
        ft = self.raw.get("frequency_test")
        if not ft or not ft.get("csv"):
            return None
        data = np.genfromtxt(self.root / ft["csv"], delimiter=",",
                             skip_header=1)
        return FrequencyData(tip_masses=data[:, 0] * 1e-3,
                             frequencies=data[:, 1], sigma=sigma)

    def ccs_data(self, sigma: float = 0.01) -> CCSData | None:
        """CCS point (``ip_g`` at ``deflection_fraction``), if measured."""
        ccs = self.raw.get("ccs")
        if not ccs or ccs.get("ip_g") is None:
            return None
        return CCSData(ip_mass=ccs["ip_g"] * 1e-3,
                       deflection_fraction=_get(ccs, "deflection_fraction",
                                                1 / 3), sigma=sigma)

    # -- images ---------------------------------------------------------------
    def frame_paths(self) -> list[Path]:
        """Static-bend frames from ``first_frame`` to ``last_frame``."""
        sb = self.raw["static_bend"]
        folder = self.root / sb["images_dir"]
        files = sorted(folder.glob("*.jpg"))
        names = [f.name for f in files]
        i0 = names.index(sb["first_frame"])
        i1 = names.index(sb["last_frame"])
        return files[i0:i1 + 1]

    def image_transform(self, **kwargs) -> ImageTransform:
        """Initial pixel-to-metre transform with priors.

        The scale guess follows ``calibration.pixel_scale_from``: with
        ``rod_length`` it is fixed later from the traced arc length (see
        :meth:`extract_bend_frames`); here a placeholder is used until then.
        """
        cal = self.raw.get("calibration", {})
        clamp = _get(cal, "clamp_px")
        if clamp is None:
            raise ValueError(f"{self.id}: calibration.clamp_px is not set")
        direction = _get(self.raw["static_bend"], "trace_direction", [-1, 0])
        return ImageTransform(clamp_px=np.asarray(clamp, float),
                              scale=kwargs.pop("scale", 1e-3),
                              rod_points_left=direction[0] < 0, **kwargs)

    def tracked_markers(self) -> np.ndarray | None:
        """Hand-tracked markers from ``static_bend.track_file``.

        Reads the tab-separated track export (columns: index, track, slice,
        x, y, ...; one track per marker, one slice per frame, both 1-based).

        Returns:
            Array ``(n_frames, n_markers, 2)`` of pixel positions, marker 1
            (the tip) first, or ``None`` without a track file.
        """
        track_file = _get(self.raw["static_bend"], "track_file")
        if track_file is None:
            return None
        rows = []
        text = (self.root / track_file).read_text(errors="ignore")
        for line in text.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 5:
                rows.append([float(v) for v in parts[1:5]])
        data = np.array(rows)
        n_tracks = int(data[:, 0].max())
        n_slices = int(data[:, 1].max())
        out = np.full((n_slices, n_tracks, 2), np.nan)
        for track, sl, x, y in data:
            out[int(sl) - 1, int(track) - 1] = (x, y)
        return out

    def extract_bend_frames(self, every: int = 1, n_points: int = 40,
                            tips: str = "auto", arc_tolerance: float = 15.0,
                            **trace_kwargs
                            ) -> tuple[list[BendFrame], float]:
        """Trace the rod in the static-bend frames.

        Args:
            every: Use every ``every``-th frame.  Frame ``k`` carries ``k``
                load steps unless ``static_bend.load_steps`` lists them per
                frame; frames in ``static_bend.exclude_frames`` are skipped.
                A ``static_bend.background`` frame (raw frames) is
                subtracted before tracing.
            n_points: Centre-line points kept per frame (resampled evenly
                along the trace).
            tips: ``"tracked"`` uses tracked marker 1 as the tip and drops
                trace points beyond it (the trace may run on along the load
                line or drawn labels).  ``"arc"`` checks traced tips against
                the inextensible rod: the clamp-to-tip arc length should be
                the same in every frame, so a traced tip more than
                ``arc_tolerance`` px from the median length is discarded
                (``tip=None``) and its points are trimmed to the median
                length.  ``"trace"`` keeps all traced tips.  ``"auto"`` uses
                tracked tips when a track file exists, else ``"arc"``.
            arc_tolerance: See ``tips="arc"`` [px].
            **trace_kwargs: Passed to
                :func:`~flycastsim.rod.imaging.extract_centerline`.

        Returns:
            ``(frames, scale)``: the frames in pixel coordinates and the
            pixel scale [m/px] from the rod length: the free length over the
            clamp-to-tip arc length (of the first frame with tracked tips,
            else the median over frames).
        """
        sb = self.raw["static_bend"]
        start = _get(sb, "trace_start_px")
        if start is None:
            raise ValueError(f"{self.id}: static_bend.trace_start_px is "
                             "not set")
        direction = _get(sb, "trace_direction", [-1, 0])
        clamp = np.asarray(self.raw["calibration"]["clamp_px"], float)
        markers = self.tracked_markers() if tips in ("auto", "tracked") \
            else None
        if tips == "tracked" and markers is None:
            raise ValueError(f"{self.id}: no track file for tracked tips")
        if tips == "auto":
            tips = "tracked" if markers is not None else "arc"
        exclude = set(_get(sb, "exclude_frames", []))
        load_steps = _get(sb, "load_steps")
        background = _get(sb, "background")
        if background is not None:
            background = load_gray(self.root / background)

        traced = []                     # (k, points, tip, arc length)
        for k, path in enumerate(self.frame_paths()):
            if k % every or k in exclude:
                continue
            trace = extract_centerline(load_gray(path), start, direction,
                                       background, **trace_kwargs)
            pts, tip = trace.points, trace.tip
            if tips == "tracked" and k < len(markers):
                tip = markers[k, 0]
                end = int(np.argmin(np.hypot(*(pts - tip).T)))
                pts = pts[:end + 1]
            path_px = np.vstack([clamp, pts, tip])
            arc = np.concatenate([[0.0], np.cumsum(
                np.hypot(*np.diff(path_px, axis=0).T))])
            traced.append((k, pts, np.asarray(tip, float), arc))

        lengths = np.array([a[-1] for *_, a in traced])
        ref = lengths[0] if tips == "tracked" else float(np.median(lengths))
        frames = []
        for (k, pts, tip, arc), length in zip(traced, lengths):
            if tips == "arc" and abs(length - ref) > arc_tolerance:
                # untrustworthy tip: drop it, keep points up to the median
                # length (arc[1:-1] are the trace points' arc positions)
                pts = pts[arc[1:-1] <= ref - arc_tolerance]
                tip = None
            idx = np.linspace(0, len(pts) - 1, min(n_points, len(pts)))
            steps = k if load_steps is None else load_steps[k]
            frames.append(BendFrame(points=pts[np.round(idx).astype(int)],
                                    load_steps=steps, tip=tip))
        return frames, self.free_length / ref


def fit_rod(meas: RodMeasurement, preset: str | dict = "full", *,
            frames: list[BendFrame] | None = None,
            scale: float | None = None, progress=None
            ) -> ProfileFitResult:
    """Fit a measured rod's stiffness and mass profiles.

    Sets up :class:`~flycastsim.rod.profile_fit.ProfileFitProblem` the way the
    bundled rods were fitted (``docs/rod_profile.rst``): per-frame tip loads,
    a rotational compliance of the strapped mount, the image transform with
    priors (clamp at the front strap ±5 px, scale from the rod length ±2 %,
    camera level ±0.1°), robust residuals, the tip-mass frequency test and
    the CCS point; measured section masses with their default priors, or a
    generic guess (±5 g) without them.

    Args:
        meas: The measurement data set.
        preset: A key of :data:`FIT_PRESETS` or a dict with the same keys.
        frames, scale: Traced frames and pixel scale from
            :meth:`RodMeasurement.extract_bend_frames` (traced here if
            ``None``; pass them to reuse a preview).
        progress: Callback ``progress(n_evaluations, cost)``, see
            :func:`~flycastsim.rod.profile_fit.fit_profile`.
    """
    settings = dict(FIT_PRESETS[preset] if isinstance(preset, str)
                    else preset)
    if frames is None:
        frames, scale = meas.extract_bend_frames(
            every=settings["every"], n_points=settings["n_points"])
    transform = meas.image_transform(scale=scale, sigma_px=1.5,
                                     clamp_sigma_px=5.0,
                                     roll_sigma=math.radians(0.1),
                                     scale_sigma_rel=0.02)
    ei_model = MonotoneLogEI(meas.clamp_s, meas.length,
                             n_coef=settings["n_coef"])
    mass_model = (meas.mass_model() if meas.sections
                  else meas.mass_model(mass_sigma=0.005))
    problem = ProfileFitProblem(
        ei_model, mass_model, meas.length, meas.clamp_s, frames,
        load_step=0.005, fit_frame_loads=True,
        frequency=meas.frequency_data(sigma=0.02),
        ccs=meas.ccs_data(sigma=0.01), smoothness=0.01,
        transform=transform, robust=3.0,
        clamp_compliance=0.01, fit_clamp_compliance=True)
    return fit_profile(problem,
                       ei_params=ei_model.params_from_endpoints(40.0, 2.0),
                       progress=progress, xtol=settings["xtol"],
                       ftol=settings["ftol"])


def export_fit(meas: RodMeasurement, result: ProfileFitResult,
               folder: str | Path, notes: list[str] | None = None,
               preset: str | dict | None = None):
    """Write a fit as a fitted-rod folder and return it as a
    :class:`~flycastsim.rod.fitted.FittedRod`.

    Writes ``rod.json`` + ``rod.csv`` (FEM component), ``fit_summary.json``
    and a copy of the measurement's ``rod.yaml``.
    """
    import yaml

    from .fitted import FittedRod

    folder = Path(folder)
    notes = list(notes or [])
    notes.append(f"clamp at s = {meas.clamp_s} m; EI behind the clamp is "
                 "held constant and EI within ~0.3 m of the tip is poorly "
                 "constrained")
    notes.append("no diameter column: the fit does not measure d")
    result.write_component(folder, f"{meas.label} - fitted rod", notes=notes)
    summary = {"rod": meas.id, "label": meas.label, "notes": notes,
               "preset": preset, **result.summary()}
    (folder / "fit_summary.json").write_text(json.dumps(summary, indent=1)
                                             + "\n")
    (folder / "rod.yaml").write_text(yaml.safe_dump(meas.raw,
                                                    sort_keys=False))
    return FittedRod.from_folder(folder)


def load_rod_measurement(path: str | Path) -> RodMeasurement:
    """Read a ``rod.yaml`` (or the folder containing one)."""
    import yaml

    path = Path(path)
    if path.is_dir():
        path = path / "rod.yaml"
    with open(path) as fh:
        raw = yaml.safe_load(fh)
    if raw.get("schema") != SCHEMA:
        raise ValueError(f"{path}: unsupported schema {raw.get('schema')!r}")
    rod = raw.get("rod", {})
    secs = rod.get("sections") or []
    sections = None
    if secs and all(s.get("mass_g") is not None for s in secs):
        sections = [RodSection.from_grams(s["mass_g"], s["length_m"],
                                          s["mass_center_m"],
                                          name=s.get("name", ""))
                    for s in secs]
    mount = raw.get("mount", {})
    return RodMeasurement(
        root=path.parent, id=raw.get("id", path.parent.name),
        label=f"{raw.get('make', '')} {raw.get('model', '')}".strip(),
        length=float(rod["length_m"]), sections=sections,
        ferrule_overlap=rod.get("ferrule_overlap_m"),
        clamp_s=float(_get(mount, "clamp_s_m", 0.0)),
        clamp_angle=math.radians(_get(mount, "clamp_angle_deg", 0.0)),
        raw=raw)
