"""
Streamlit main app for FlyCasting simulator
"""
import time

import streamlit as st
import numpy as np
# from skimage.draw import line_aa, rectangle_perimeter, circle_perimeter_aa
# import pandas as pd
# from PIL import Image, ImageDraw

from flycast import brick_spring_simple, plot_brick_spring
from flycast import BrickSpringAnim



st.sidebar.title("Select section")
topic = st.sidebar.selectbox(
    "",
    (("Introduction", 0), ("Simple 1D model", 1),
     ("Flyline model", 2)),
    format_func=lambda x: x[0]
)

show_intro = st.sidebar.checkbox("Show intro?", value=True)

if topic[1] == 0:
    st.title("Flycast simulator")
    st.write("""
             This is the start of an open and free flycasting
             simulator.
             
             The simulator is both an app (which is probably what
             you are looking at) and a library which you can use
             and extend as you like.
             
             The simulator and library is a work in progress which
             will be  developed in an ad-hock fashion when I have
             the time and inspiration.
             
             #### At the moment the simulator contains:
             1. A simple 1-D model for casting
             
             #### The following is planned but not implemented:
             1. A fly line dynamics model
             1. A fly rod dynamics model
             1. A linked line and rod model
             """)

elif topic[1] == 1:
    # Widget for brick-spring-car model
    st.write("""
    # Simple 1-D casting model
    Simulation using a simple 1-D (toy) model of casting
    (a car pulling a brick using a linear spring).
    
    You can *play with the parameters* to get a feeling for 
    how various line weight, rod stiffness, input, etc.
    affects the cast and line launch speed.
    """)

    if show_intro:
        st.write("""
        ## Brick-spring-car model
        """)
        st.image("./doc/fig/brick_spring.png")
        st.write("""
        The "simplest possible" (limited) model for a fly cast
        (or spin cast) is probably the *brick-spring-car*
        model. 
        
        In this model the line is replaced by a "brick" which
        is pulled along an imaginary frictionless surface
        by an imaginary car connected by a spring.
        The movement of the car mimics rod leverage, and
        the spring mimics the elastic bending and un-bending
        of the rod. 
        
        The model is solved numerically (with tunable
        parameters and driving), and you can play with the
        parameters in the model.  
        
        This can be used to understand and get a feeling for:
        * The relation and interplay of "leverage" and "spring"
        * Understanding the effect of hard and soft stops
        * Understanding the importance of "work path"
         
        This model is of course not super original as it is
        just a simple forced harmonic oscillator model;
        one of the most *used* and *abused* models in physics...
        
        You'll be able to tune and change the input parameters
        in the sidebar. The corresponding results will be
        plotted and animated below.
        """)


    # Set up adjustable simulation parameters
    show_simulation = st.sidebar.checkbox("Show simulation")
    st.sidebar.write("## Adjust simulation parameters")
    k = st.sidebar.slider("Spring stiffness [N/m]", 0.5, 3.0, 1.0, 0.1)
    m = st.sidebar.slider("Brick mass [g]", 5, 40, 10, 1)
    m /= 1000.0 # , format="%0.03f")
    c_max_speed = st.sidebar.slider("Car max speed [m/s]", 3.0, 40.0, 18.0, 1.0, format="%0f")
    c_turn_t = st.sidebar.slider("Stop acceleration time [s]", 0.05, 1.0, 0.3, 0.01)
    c_stop_t = st.sidebar.slider("Full stop time [s]", 0.05, 1.0, 0.45, 0.01)
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

    st.write("### Simulation results:")

    if len(plot_cols) == 0:
        plot_cols = [_c[0] for _c in show_columns if _c[0].endswith("speed")]

    fig = plot_brick_spring(res, plot_cols)
    st.plotly_chart(fig)

    # Animation work in progress
    if show_simulation:
        anim = BrickSpringAnim(res, cols=plot_cols)
        image = st.empty()
        for _im in anim:
            image.image(_im)
            time.sleep(0.05)


elif topic[1] == 2:
    st.write("""
    # Placeholder for coming line model
    When the model for fly line flight is "ready"
    it will be displayed here.
    """)
