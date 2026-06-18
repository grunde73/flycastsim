"""
Package with tools for simulating fly casts
"""

from .brick_spring import simple_sim as brick_spring_simple
from .brick_spring_helpers import plot_brick_spring
from .brick_spring_helpers import animate_brick_spring
from .brick_spring_helpers import BrickSpringAnim
from .fem_helpers import animate_fly_cast, plot_cast_snapshots
from . import fem

__version__ = "0.0.2"
