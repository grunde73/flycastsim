"""Loading of bundled example fly-rod datasets.

The example rods are the worked examples from Løvoll & Angus,
*"Measuring fly rod swingweight"* (2008, ``data/swingweight.pdf``).  They ship
**inside the package** at ``flycastsim/data/rods/example_rods.json`` so they are
importable from an installed wheel via :mod:`importlib.resources`, and are used
both as Streamlit presets and as test fixtures.

Measured rods with no published swingweight ship next to them, as one CSV file
per rod listed in ``measured_rods.json`` (:func:`load_measured_rods`).  Their
estimates are not validated against a reference, so they are kept apart from
the worked examples.  :func:`check_consistency` compares their section data
with the measured overall mass and balance point.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from .swingweight import RodSection

#: Package sub-path holding the bundled rod datasets.
_DATA_PACKAGE = "flycastsim.data.rods"
_EXAMPLE_FILE = "example_rods.json"
_MEASURED_FILE = "measured_rods.json"
#: Expected header of a swingweight measurement CSV file.
_CSV_HEADER = ["length[m]", "mass_center[m]", "mass[g]"]


@dataclass
class ExampleRod:
    """A bundled example rod with its measured sections and reference value.

    Attributes:
        make: Manufacturer (e.g. ``"Sage"``).
        model: Model / size designation (e.g. ``"Z-Axis 590-4"``).
        has_reel_seat: Whether the rod is a finished rod (reel seat + grip
            present) or a bare blank.
        assembled_length: Measured length of the assembled rod [m].
        sections: Measured sections, butt to tip (:class:`RodSection`, SI).
        reference_swingweight_gm2: Swingweight reported in the paper
            [:math:`g\\,m^2`], for validation.
    """

    make: str
    model: str
    has_reel_seat: bool
    assembled_length: float
    sections: list
    reference_swingweight_gm2: float

    @property
    def label(self) -> str:
        """``"Make Model"`` display label."""
        return f"{self.make} {self.model}"


def load_example_rods() -> list:
    """Load the bundled example rods.

    Returns:
        A list of :class:`ExampleRod`, in file order.
    """
    raw = (resources.files(_DATA_PACKAGE) / _EXAMPLE_FILE).read_text(
        encoding="utf-8")
    data = json.loads(raw)
    rods = []
    for rod in data["rods"]:
        sections = [
            RodSection.from_grams(
                mass_g=s["mass_g"], length=s["length"],
                mass_center=s["mass_center"], name=s.get("name", ""))
            for s in rod["sections"]
        ]
        rods.append(ExampleRod(
            make=rod["make"], model=rod["model"],
            has_reel_seat=rod["has_reel_seat"],
            assembled_length=rod["assembled_length"],
            sections=sections,
            reference_swingweight_gm2=rod["reference_swingweight_gm2"]))
    return rods


@dataclass
class MeasuredRod:
    """A measured rod, with its overall measurements instead of a reference.

    Args:
        id: Short identifier (e.g. ``"PA905"``).
        make: Manufacturer, empty if unknown.
        model: Model / size designation, empty if unknown.
        has_reel_seat: Whether the rod is a finished rod (reel seat + grip
            present) or a bare blank.
        assembled_length: Measured length of the assembled rod [m].
        sections: Measured sections, butt to tip (:class:`RodSection`, SI).
        measured_mass: Measured mass of the assembled rod [kg].
        measured_balance_point: Measured balance point of the assembled rod,
            taken as the distance from the rod butt [m].
        note: Free-text remark on the data, empty if there is none.
    """

    id: str
    make: str
    model: str
    has_reel_seat: bool
    assembled_length: float
    sections: list
    measured_mass: float
    measured_balance_point: float
    note: str = ""

    @property
    def label(self) -> str:
        """``"Make Model"`` display label."""
        return f"{self.make} {self.model}".strip() or self.id


@dataclass
class MeasurementConsistency:
    """Section data against the overall measurements (SI units).

    The differences are calculated minus measured.
    """

    section_mass: float
    measured_mass: float
    balance_point: float
    measured_balance_point: float

    @property
    def mass_difference(self) -> float:
        """Summed section mass minus measured overall mass [kg]."""
        return self.section_mass - self.measured_mass

    @property
    def balance_point_difference(self) -> float:
        """Calculated minus measured overall balance point [m]."""
        return self.balance_point - self.measured_balance_point


def _parse_swingweight_csv(text: str, *, source: str, **metadata) -> MeasuredRod:
    """Parse the text of a swingweight measurement CSV file."""
    lines = [line for line in text.splitlines()
             if line.strip() and not line.startswith("#")]
    rows = list(csv.reader(lines))
    if not rows or [c.strip() for c in rows[0]] != _CSV_HEADER:
        raise ValueError(
            f"{source}: expected the header {','.join(_CSV_HEADER)}.")
    if len(rows) < 3:
        raise ValueError(
            f"{source}: expected an overall rod row and at least one section "
            "row.")
    try:
        (length, balance, mass_g), *tip_to_butt = [
            [float(c) for c in row] for row in rows[1:]]
        sections = [RodSection.from_grams(sec_mass_g, sec_length, sec_center)
                    for sec_length, sec_center, sec_mass_g
                    in reversed(tip_to_butt)]
    except ValueError as exc:
        raise ValueError(f"{source}: malformed row ({exc}).") from exc
    return MeasuredRod(assembled_length=length, sections=sections,
                       measured_mass=mass_g / 1000.0,
                       measured_balance_point=balance, **metadata)


def load_swingweight_csv(path: str | Path) -> MeasuredRod:
    """Load a swingweight measurement CSV file.

    The file holds ``#`` comment lines, the header
    ``length[m],mass_center[m],mass[g]``, one row for the overall rod and then
    one row per section, **tip to butt**.

    Args:
        path: The CSV file.  Its stem becomes the rod ``id``; the make and model
            are left empty, and the rod is assumed to be a finished rod.

    Returns:
        A :class:`MeasuredRod`, with sections ordered butt to tip.

    Raises:
        ValueError: If the file is malformed.
    """
    path = Path(path)
    return _parse_swingweight_csv(
        path.read_text(encoding="utf-8"), source=str(path), id=path.stem,
        make="", model="", has_reel_seat=True)


def load_measured_rods() -> list:
    """Load the bundled measured rods.

    Returns:
        A list of :class:`MeasuredRod`, in the order of ``measured_rods.json``.
    """
    root = resources.files(_DATA_PACKAGE)
    data = json.loads((root / _MEASURED_FILE).read_text(encoding="utf-8"))
    return [
        _parse_swingweight_csv(
            (root / rod["file"]).read_text(encoding="utf-8"),
            source=rod["file"], id=rod["id"], make=rod["make"],
            model=rod["model"], has_reel_seat=rod["has_reel_seat"],
            note=rod["note"])
        for rod in data["rods"]
    ]


def check_consistency(rod: MeasuredRod) -> MeasurementConsistency:
    """Compare a rod's sections with its overall measurements.

    The balance point is the mass-weighted mean of the section balance points,
    using the measured butt balance point and the ferrule-corrected distances
    of Løvoll & Angus (2008, eqs. 2-5).  This composite calculation is not in
    the paper.  Unlike the estimator, it does not apply the reel-seat
    correction, because the measured values include the reel seat and grip.

    Differences are reported and never rejected.

    Args:
        rod: The measured rod.

    Returns:
        A :class:`MeasurementConsistency`.
    """
    n_ferrules = len(rod.sections) - 1
    sum_length = sum(s.length for s in rod.sections)
    overlap = ((sum_length - rod.assembled_length) / n_ferrules
               if n_ferrules > 0 else 0.0)
    section_mass = sum(s.mass for s in rod.sections)
    moment = 0.0
    cumulative_length = 0.0
    for i, sec in enumerate(rod.sections):
        moment += sec.mass * (cumulative_length + sec.mass_center - i * overlap)
        cumulative_length += sec.length
    return MeasurementConsistency(
        section_mass=section_mass, measured_mass=rod.measured_mass,
        balance_point=moment / section_mass,
        measured_balance_point=rod.measured_balance_point)
