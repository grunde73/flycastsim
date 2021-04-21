# -*- coding: utf-8 -*-
"""Functions for unit testing of simple brick-spring-car model
"""
import numpy as np
from flycast import brick_spring_simple


def test_against_analytic():
    """Test results from simulators against
    analytic known solutions for forced harmonic oscillator 
    """
    # Initial conditions
    k = 0.9  # Spring constant
    m = 0.01 # Brick mass
    d0 = 1.0 # Initial spring deflection
    init_con = [0, 0] # Brick starting pos and start speed
    times = [1.0, 0.3] # [end_integration_time peak_car_speed_time end_car_speed_time]
    car_speeds = [0, 0, 0] #  [car_start_speed car_peak_speed car_end_speed]

    # Starting from rest
    df = brick_spring_simple(k, m, d0, init_con, times, car_speeds)
    t1 = np.array(df.index)

    # Analytic solution
    xa1 = d0 - d0 * np.cos(np.sqrt(k/m) * t1)
    va1 = d0 * np.sqrt(k/m) * np.sin(np.sqrt(k/m) * t1)
    assert np.allclose(xa1, df["x"], rtol=1e-03)
    assert np.allclose(va1, df["v"], rtol=1e-03)

    # Brick moving initially
    init_con = [0, 10]   # Move at 10 m/s initially
    df = brick_spring_simple(k, m, d0, init_con, times, car_speeds)
    #  Analytic solution...
    d1 = np.sqrt(d0**2 + (m/k) * 10**2)
    t2 = np.array(df.index)
    phase = np.arccos(d0/d1)
    xa2 = d0 - d1 * np.cos(np.sqrt(k/m) * t2 + phase)
    va2 = d1 * np.sqrt(k/m) * np.sin(np.sqrt(k/m) * t2 + phase)
    assert np.allclose(xa2, df["x"], rtol=1e-03)
    assert np.allclose(va2, df["v"], rtol=1e-03)

    # Car moves at constant speed 10 m/s
    times = [0.7, 0.3, 0.7]
    car_speeds = [10, 10, 10]
    df = brick_spring_simple(k, m, d0, init_con, times, car_speeds)
    t3 = np.array(df.index)
    # Analytic solution
    xa3 = d0 + (10 * t3) - d0 * np.cos(np.sqrt(k/m) * t3)
    va3 = 10 + d0 * np.sqrt(k/m) * np.sin(np.sqrt(k/m) * t3)
    assert np.allclose(xa3, df["x"], rtol=1e-03)
    assert np.allclose(va3, df["v"], rtol=1e-03)