"""
Python implementation of 1d simplistic brick-spring-car
model of casting.

The simulation is in principle just a 1d forced harmonic
oscillator where the forcing can be an arbitrary
function.

Originally implemented in Matlab in 2007 or something :)
"""

from collections import namedtuple
import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp


def dydt(t, y, k, m, x_car):
    """First and second derivative of position as
    function of time.
    Args:
        t: time
        y: [x, v]
        k: spring stiffness
        m: brick mass
        x_car: function giving car position as function of time
    Returns:
        [v(t), a(t)]
    """
    dydt2 = -(k/m) * (y[0] - x_car(t))
    return y[1], dydt2


def simple_sim(k, m, d0, init_cond, times, car_speeds) -> pd.DataFrame:
    """Simple brick-spring-car simulation
    Forced harmonic oscillator where a brick is attached
    to a linear spring and towed by a car on a frictionless
    surface. The forcing is a simple triangular car speed
    profile.

    The function uses an ODE solver from Scipy for this.

    The numerical integration terminates when the brick
    overtakes the car.

    Args:
        k: Spring constant (spring stiffnes) [N/m]
        m: Mass of brick [kg]
        d0: Initial spring extension [m]
        init_cond: Initial brick condition [x(t0), v(t0)]
        times: Boundary conditions [simulation end time, car "turn time", car end time]
        car_speeds: Boundary conditions [car start speed, car peak speed, car end speed]

    Returns:
        A time indexed Pandas.DataFrame with the results from the simulation
    """

    def car_tr_pos(t):
        """Car position as function of time for triangular
        speed profile
        """
        if t <= t_turn:
            xbt = cv0 * t + 0.5 * a1 * t**2 + d0
        elif t > t_turn and t <= t_car_end:
            xbt = cv0 * t_turn + 0.5 * a1 * t_turn**2 + d0 + \
                  (a1 * t_turn) * (t - t_turn) + \
                  0.5 * a2 * (t - t_turn)**2
        else:
            xbt = car_tr_pos(t_car_end) + \
                  car_speeds[2] * (t - t_car_end)
        return xbt


    def car_tr_speed(t):
        """Car speed ad function of time for triangular
        speed profile"""
        if t <= t_turn:
            return cv0 + a1 * t
        elif t_turn < t <= t_car_end:
            return cv0 + a1 * t_turn + a2 * (t - t_turn)
        else:
            return car_speeds[2]

    def event(t, y, *args):
        return car_tr_pos(t) - y[0]
    event.terminal = True
    event.direction = -1.0

    # "Turing time"
    t_turn = times[1]

    if len(times) > 2:
        t_car_end = times[2]
    else:
        t_car_end = times[0]

    time_int = [0, times[0]]
    cv0 = car_speeds[0] # Initial car speed

    # Car acceleration
    a1 = (car_speeds[1] - car_speeds[0]) / t_turn

    # Car deceleration
    if (t_car_end > t_turn):
        a2 = (car_speeds[2] - car_speeds[1]) / (t_car_end - t_turn)
    elif t_car_end == t_turn:
        a2 = 0 # This mean an "imediate stop"...
    else:
        raise ParameterError('The car end time cannot be before turning time')

    # Run the ODE solver
    t_vec = np.linspace(time_int[0], time_int[1], 1000)
    sol = solve_ivp(dydt, time_int, init_cond,
                    t_eval=t_vec, events=event,
                    args=(k, m, car_tr_pos))

    cx = np.array([car_tr_pos(_t) for _t in sol.t])   # Car position
    cv = np.array([car_tr_speed(_t) for _t in sol.t]) # Car speed
    sd = cx - sol.y[0]                                # Spring extension

    return pd.DataFrame({'x': sol.y[0], 'v': sol.y[1],
                       'car_pos': cx,
                       'car_speed': cv,
                       'sp_ext': sd,
                       'sp_e': 0.5 * k * sd**2,         # Spring energy
                       'car_p': k * cv * sd,            # Car power
                       'brick_e': 0.5 * m * sol.y[1]**2 # Brick energy
                       },
                      index=sol.t)