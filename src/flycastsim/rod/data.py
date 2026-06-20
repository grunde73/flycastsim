"""Loading of bundled example fly-rod datasets.

The example rods are the worked examples from Løvoll & Angus,
*"Measuring fly rod swingweight"* (2008, ``data/swingweight.pdf``).  They ship
**inside the package** at ``flycastsim/data/rods/example_rods.json`` so they are
importable from an installed wheel via :mod:`importlib.resources`, and are used
both as Streamlit presets and as test fixtures.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources

from .swingweight import RodSection

#: Package sub-path holding the bundled rod datasets.
_DATA_PACKAGE = "flycastsim.data.rods"
_EXAMPLE_FILE = "example_rods.json"


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
