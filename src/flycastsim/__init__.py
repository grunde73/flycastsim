"""
Package with tools for simulating fly casts
"""

from . import fem, rod, sho
from .fem_helpers import (
                          animate_fly_cast,
                          load_cast1_frames,
                          plot_cast_snapshots,
                          plot_cast_speeds,
                          plot_chord_comparison,
                          plot_tip_deflection,
)
from .rod import (
                          RodSection,
                          SectionResult,
                          SwingweightResult,
                          load_example_rods,
                          plot_swingweight_contributions,
)
from .rod import compute_swingweight as swingweight
from .sho import BrickSpringAnim, animate_brick_spring, plot_brick_spring
from .sho import simple_sim as brick_spring_simple

__version__ = "0.0.2"
