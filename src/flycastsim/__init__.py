"""
Package with tools for simulating fly casts
"""

from .sho import simple_sim as brick_spring_simple
from .sho import plot_brick_spring
from .sho import animate_brick_spring
from .sho import BrickSpringAnim
from .fem_helpers import (animate_fly_cast, plot_cast_snapshots,
                          plot_chord_comparison, load_cast1_frames)
from . import fem
from . import sho

__version__ = "0.0.2"
