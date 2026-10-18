"""Fitted rods: stiffness/mass profiles from the rod profile fit, ready to use.

A fitted rod is a folder holding

* ``rod.json`` + ``rod.csv`` -- an FEM component
  (:func:`flycastsim.fem.components.load_component`) with the fitted
  ``EI(s)`` and ``mu(s)`` from butt to tip, and
* ``fit_summary.json`` -- the fitted parameters and the data they were fitted
  to (:meth:`flycastsim.rod.profile_fit.ProfileFitResult.summary`).

Such folders are written by :func:`flycastsim.rod.measurement.export_fit`;
the rods fitted to the bundled measurements (PA905, XP590, TCR590) ship with
the package in ``data/components/fitted_rods/`` and are listed by
:func:`load_fitted_rods`.  :class:`FittedRod` gives the profiles as
functions, the swingweight, and the fitted bend shapes for plotting, so
bundled rods and rods fitted at run time are handled alike.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

import numpy as np

from ..fem.components import Component, load_component
from .elastica import GRAVITY, solve_cantilever_fd
from .profile_fit import ImageTransform, MonotoneLogEI, SectionMassModel

#: Package folder holding the bundled fitted rods.
_FITTED_RODS = ("data", "components", "fitted_rods")


@dataclass
class FittedRod:
    """A fitted rod: FEM component plus fit summary.

    Attributes:
        id: Short identifier (folder name, e.g. ``"XP590"``).
        label: Human-readable name.
        folder: Folder holding ``rod.json``, ``rod.csv`` and
            ``fit_summary.json``.
        component: The rod as an FEM component (``d`` may be all zero: the
            fit does not measure the diameter).
        summary: Contents of ``fit_summary.json`` (empty if missing).
    """

    id: str
    label: str
    folder: Path
    component: Component
    summary: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_folder(cls, folder: str | Path) -> "FittedRod":
        """Load a fitted-rod folder."""
        folder = Path(folder)
        component = load_component(folder / "rod.json")
        summary_path = folder / "fit_summary.json"
        summary = (json.loads(summary_path.read_text())
                   if summary_path.exists() else {})
        return cls(id=summary.get("rod", folder.name),
                   label=summary.get("label", component.name),
                   folder=folder, component=component, summary=summary)

    # -- profiles -------------------------------------------------------------
    @property
    def length(self) -> float:
        return self.component.length

    @property
    def s_clamp(self) -> float:
        return float(self.summary.get("s_clamp_m", 0.0))

    def __post_init__(self):
        # Exact fitted profiles from the summary's parameters when present;
        # otherwise interpolate the component table (log-linear for EI).
        sm = self.summary
        self._EI = self._mu = None
        if "ei_spline_params" in sm and "ei_model" in sm:
            model = MonotoneLogEI(sm["s_clamp_m"], sm["length_m"],
                                  n_coef=sm["ei_model"]["n_coef"],
                                  degree=sm["ei_model"]["degree"])
            self._EI = model.stiffness(np.asarray(sm["ei_spline_params"]))
        if "mass_model" in sm and "section_mass_kg" in sm:
            mm = sm["mass_model"]
            masses = sm["section_mass_kg"]
            centers = sm["section_mass_center_m"]
            model = SectionMassModel(
                lengths=mm["lengths"], ferrule_overlap=mm["ferrule_overlap"],
                masses=masses, mass_centers=centers,
                has_reel_seat=mm["has_reel_seat"], l_rg=mm["l_rg"])
            self._mu = model.density()

    def EI(self, s):
        """Bending stiffness [N m^2] at ``s`` from the butt."""
        if self._EI is not None:
            return self._EI(s)
        return np.exp(np.interp(s, self.component.s,
                                np.log(self.component.EI)))

    def mu(self, s):
        """Mass per unit length [kg/m] at ``s`` from the butt."""
        if self._mu is not None:
            return self._mu(np.asarray(s, dtype=float))
        return np.interp(s, self.component.s, self.component.m)

    @property
    def swingweight_gm2(self) -> float:
        """Butt-axis moment of inertia of the fitted mass profile [g m^2]."""
        s = np.linspace(0.0, self.length, 2001)
        return 1e3 * float(np.trapezoid(self.mu(s) * s**2, s))

    @property
    def mass_g(self) -> float:
        """Total rod mass of the fitted profile [g]."""
        s = np.linspace(0.0, self.length, 2001)
        return 1e3 * float(np.trapezoid(self.mu(s), s))

    # -- fitted data ------------------------------------------------------------
    def _transform(self) -> ImageTransform | None:
        tr = self.summary.get("image_transform")
        if tr is None:
            return None
        return ImageTransform(
            clamp_px=np.asarray(tr["clamp_px"], float),
            scale=float(tr["scale_m_per_px"]),
            roll=float(tr["camera_roll_rad"]),
            clamp_angle_offset=float(tr["clamp_angle_offset_rad"]),
            rod_points_left=bool(tr.get("rod_points_left", True)))

    def bend_frames(self, n: int = 200) -> list[dict]:
        """Observed and fitted shapes of the static-bend frames.

        Returns one dict per frame with ``points`` (observed centre line),
        ``tip`` (observed tip or ``None``), ``model`` (``(n, 2)`` fitted rod
        shape), ``added_mass_kg`` and ``load_steps``, all in the frames'
        coordinates (pixels, ``y`` down, if an image transform was fitted;
        see ``summary["frame_units"]``).  Empty without a summary.
        """
        frames = self.summary.get("frames", [])
        if not frames:
            return []
        tr = self._transform()
        p0 = None if tr is None else tr.initial_params()
        offset = 0.0 if tr is None else tr.clamp_angle_offset
        compliance = self.summary.get("clamp_compliance_rad_per_Nm", 0.0)
        loads = self.summary["frame_added_mass_kg"]
        out, guess = [], None
        for frame, added in zip(frames, loads):
            mass = frame.get("known_mass_kg", 0.0) + added
            sol = solve_cantilever_fd(
                self.EI, self.mu, length=self.length, s_clamp=self.s_clamp,
                tip_load=mass * GRAVITY,
                clamp_angle=frame.get("clamp_angle_rad", 0.0) + offset,
                clamp_compliance=compliance, guess=guess)
            guess = sol
            model = sol.at(np.linspace(self.s_clamp, self.length, n))[:2].T
            if tr is not None:
                model = tr.to_pixels(p0, model)
            out.append({"points": np.asarray(frame["points"]),
                        "tip": (None if frame.get("tip") is None
                                else np.asarray(frame["tip"])),
                        "model": model, "added_mass_kg": added,
                        "load_steps": frame["load_steps"]})
        return out


def fitted_rods_folder() -> Path:
    """Folder of the bundled fitted rods."""
    return Path(str(resources.files("flycastsim").joinpath(*_FITTED_RODS)))


def load_fitted_rods() -> list[FittedRod]:
    """The fitted rods bundled with the package, sorted by id."""
    base = fitted_rods_folder()
    return [FittedRod.from_folder(p) for p in sorted(base.iterdir())
            if (p / "rod.json").exists()]
