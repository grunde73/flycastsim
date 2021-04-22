import streamlit as st
import cufflinks as cf

from flycast import brick_spring_simple

st.title("Flycast simulator")
st.write("""
This is the start of an open and free flycasting simulator.

The app is a work in process and it will be developed in an ad-hock
fashion when I have the time.
The project will also be used to learn and get practical experience
using the Streamlit framework.
""")

# Add widget for brick-spring-car model
# import pandas as pd

st.write("""
## Understanding leverage and spring
A good model to simulate and understand the 
contribution and interaction between rod leverage (rod
rotation to line-speed) and rod spring (rod loading and
un-loading) is the *brick-spring-car* model.

In this model the line is replaced by a "brick" which
is pulled along an imaginary frictionless surface
by an imaginary car connected by a spring.
The movement of the car mimics rod leverage, and
the spring mimics the elastic bending and un-bending
of the rod. 

FIXME: Add figure here.

The model is solved numerically, and you can play
with the parameters in the model. 

This model is of course just a simple forced harmonic
oscillator model, the most used and abused model in physics.
""")

# Set up adjustable simulation parameters
st.sidebar.write("Adjust simulation parameters")
k = st.sidebar.slider("Spring stiffness ", 0.5, 3.0, 1.0, 0.1)
m = st.sidebar.slider("Brick mass", 0.005, 0.04, 0.01, 0.001, format="%0.03f")
c_max_speed = st.sidebar.slider("Car max speed", 3.0, 30.0, 18.0, 1.0, format="%0f")
c_turn_t = st.sidebar.slider("Stop acceleration time", 0.05, 1.0, 0.3, 0.01)
c_stop_t = st.sidebar.slider("Full stop time", 0.05, 1.0, 0.45, 0.01)
if c_stop_t <= c_turn_t:
    st.sidebar.warning("stop time forced to turn time + 0.01s")
    c_stop_t = c_turn_t + 0.01

d0 = 0
start_cond = [0, 0]  # [x(t0), v(t0)]
ts = [2.0, c_turn_t, c_stop_t]  # [sim_tmax, t_break, t_stop]
vct = [0, c_max_speed, 0]  # [v_car(t0), v_car_max, v_car_end]

# Run simulation
res = brick_spring_simple(k, m, d0, start_cond, ts, vct)
# st.write(res.columns)

speed_fig = res.loc[:, ['brick speed', 'car speed']].iplot(asFigure=True,
                                                 xTitle=r"$Time\ \ [s]$",
                                                 yTitle=r"$Speed\ \ [m/s]$")
st.plotly_chart(speed_fig)

# st.write("Energy in brick and in spring as function of time")
energy_fig = res.loc[:, ['spring energy', 'brick energy']].iplot(asFigure=True,
                                  xTitle=r"$Time\ \ [s]$",
                                  yTitle=r"$Energy\ \ [J]$")
st.plotly_chart(energy_fig)

# st.write("Force and power from car on brick")

### FIXME: make multiple plots thingy

# force_fig = res.loc[:, ['sp_e', 'brick_e']].iplot(asFigure=True,
#                                   xTitle=r"$Time\ \ [s]$",
#                                   yTitle=r"$Energy\ \ [J]$")
# force_fig = cf.Figure()
# force_fig.set_subplots(rows=2, cols=1, shared_xaxes=True)
# force_fig.add_trace(res.loc[:, ['force',]].figure(yTitle=r"$Force\ \ [N]$"))
# force_fig.add_trace(res.loc[:,['car_p',]].figure(yTitle=r"$Power\ \ [W]$",
#                                                  xTitle=r"$Time\ \ [s]$"))
# st.plotly_chart(force_fig)