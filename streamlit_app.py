"""
Streamlit main app for FlyCasting simulator
"""

import streamlit as st
# import numpy as np
# from skimage.draw import line_aa, circle, rectangle

from flycast import brick_spring_simple, plot_brick_spring



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
c_max_speed = st.sidebar.slider("Car max speed", 3.0, 40.0, 18.0, 1.0, format="%0f")
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

# Capture returned columns and select for plotting
show_columns = []
st.sidebar.write("Plot columns:")
for c in res.columns:
    show_columns.append((c, st.sidebar.checkbox(c)))

plot_cols = [_c[0] for _c in show_columns if _c[1]]
st.write("Simulation results")

if len(plot_cols) == 0:
    plot_cols = [_c[0] for _c in show_columns if _c[0].endswith("speed")]

fig = plot_brick_spring(res, plot_cols)
st.plotly_chart(fig)


### Working here
# # Animation work in progress
# h, w = 640, 400
# image = st.empty()
# image.image(np.ones((h, w)) - 0.2)