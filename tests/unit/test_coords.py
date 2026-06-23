"""Tests for the kinematics helpers in :mod:`flycastsim.fem.coords`.

These cover the speed/index helpers used by the dashboard speed graph
(rod-tip, line and imaginary rigid-lever speeds).  They use simple synthetic
motions with known analytic speeds rather than the full solver.
"""
import numpy as np

from flycastsim.fem import (node_speed, node_index_from_tip, rigid_lever_tip,
                            rigid_lever_speed)


def test_node_speed_constant_velocity():
    """A node moving at constant velocity has constant, known speed."""
    t = np.linspace(0.0, 1.0, 11)
    n_nodes = 3
    X = np.zeros((t.size, n_nodes))
    Y = np.zeros((t.size, n_nodes))
    # node 1 moves at (3, 4) m/s -> speed 5
    X[:, 1] = 3.0 * t
    Y[:, 1] = 4.0 * t
    speed = node_speed(t, X, Y, 1)
    assert speed.shape == t.shape
    np.testing.assert_allclose(speed, 5.0, rtol=1e-12, atol=1e-12)
    # a stationary node has zero speed
    np.testing.assert_allclose(node_speed(t, X, Y, 0), 0.0, atol=1e-12)


def test_node_speed_handles_non_uniform_time():
    """np.gradient-based speed is correct on a non-uniform time grid."""
    t = np.array([0.0, 0.1, 0.35, 0.9, 1.0])
    X = np.outer(2.0 * t, [0.0, 1.0])  # node 1 at x = 2 t
    Y = np.zeros_like(X)
    np.testing.assert_allclose(node_speed(t, X, Y, 1), 2.0, rtol=1e-12)


def test_node_index_from_tip_basic_and_clamp():
    """Index selection measures back from the tip and clamps to the region."""
    s = np.linspace(0.0, 10.0, 11)  # s[i] == i
    # 0 m from the tip is the last node
    assert node_index_from_tip(s, 0.0) == 10
    # 3 m back from the tip -> s = 7 -> node 7
    assert node_index_from_tip(s, 3.0) == 7
    # restricting the region: tip of [5, 11) is node 10, 2 m back -> node 8
    assert node_index_from_tip(s, 2.0, start=5, stop=11) == 8
    # a distance larger than the region clamps to the region start
    assert node_index_from_tip(s, 100.0, start=5, stop=11) == 5


def test_rigid_lever_tip_geometry():
    """The lever tip sits one length along the butt tangent from the handle."""
    X = np.array([[1.0, 9.0], [2.0, 9.0]])  # handle (node 0) moves x: 1 -> 2
    Y = np.array([[0.0, 9.0], [0.5, 9.0]])  # handle y: 0 -> 0.5
    angle = np.array([0.0, np.pi / 2])
    xr, yr = rigid_lever_tip(X, Y, angle, length=2.0)
    np.testing.assert_allclose(xr, [1.0 + 2.0, 2.0 + 0.0])
    np.testing.assert_allclose(yr, [0.0 + 0.0, 0.5 + 2.0])


def test_rigid_lever_speed_pure_rotation():
    """For a fixed handle, lever-tip speed equals length * |dtheta/dt|."""
    t = np.linspace(0.0, 1.0, 101)
    omega = 2.0  # rad/s
    length = 3.0
    n_nodes = 2
    X = np.zeros((t.size, n_nodes))  # handle fixed at origin
    Y = np.zeros((t.size, n_nodes))
    angle = omega * t
    speed = rigid_lever_speed(t, X, Y, angle, length)
    # interior points are accurate; endpoints use one-sided differences
    np.testing.assert_allclose(speed[1:-1], length * omega, rtol=1e-3)
