"""
Streamlit main app for FlyCasting simulator
"""
import time
import pandas as pd
import streamlit as st
from PIL import ImageFont

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

             The full sourcecode is available on GitHub
             [https://github.com/grunde73/flycastsim](https://github.com/grunde73/flycastsim).
             
             
             ## Disclaimer
              
             > "Essentially, all models are wrong, but some are useful."
             >
             > George E. P. Box
             
             Remember, models are just models. So be critical and aware
             of the limitations and assumptions of all models, including
             the ones found here :-D
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
        st.image("./docs/fig/brick_spring.png")
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
        
        The full sourcecode is available on GitHub
        [https://github.com/grunde73/flycastsim](https://github.com/grunde73/flycastsim).
        
       
        """)


    # Set up adjustable simulation parameters
    show_simulation = st.sidebar.checkbox("Show animation")
    # Default/baseline parameters
    k_d = 1.0 # 1 N/m

    st.sidebar.write("## Adjust simulation parameters")
    k = st.sidebar.slider("Spring stiffness [N/m]", 0.5, 3.0, k_d, 0.1)
    m_d = 10 # 10g
    m = st.sidebar.slider("Brick mass [g]", 5, 40, m_d, 1)
    m_d /= 1000.0
    m /= 1000.0   # from g to kg
    c_max_speed_d = 18.0 # m/s
    c_max_speed = st.sidebar.slider("Car max speed [m/s]", 3.0, 40.0,
                                    c_max_speed_d, 1.0, format="%0f")

    c_turn_t_d = 0.3 # [s]
    c_turn_t = st.sidebar.slider("Stop acceleration time [s]", 0.05,
                                 1.0, c_turn_t_d, 0.01)
    c_stop_t_d = 0.45 # [s]
    c_stop_t = st.sidebar.slider("Full stop time [s]", 0.05, 1.0,
                                 c_stop_t_d, 0.01)

    if c_stop_t <= c_turn_t:
        st.sidebar.warning("stop time forced to turn time + 0.01s")
        c_stop_t = c_turn_t + 0.01

    d0 = 0
    start_cond = (0, 0)  # [x(t0), v(t0)]
    ts = (2.0, c_turn_t, c_stop_t)  # [sim_tmax, t_break, t_stop]
    vct = (0, c_max_speed, 0)  # [v_car(t0), v_car_max, v_car_end]

    # Default settings
    ts_d = (2.0, c_turn_t_d, c_stop_t_d)
    vct_d = (0, c_max_speed_d, 0)

    # Run with default
    @st.cache
    def _cache_default():
        _res = brick_spring_simple(k_d, m_d, d0, start_cond, ts_d, vct_d)
        _res.columns = ["base " + _c for _c in _res.columns]
        return _res
    res_d = _cache_default()

    # Run simulation
    if ts != ts_d or vct_d != vct or k_d != k or m_d != m:
        is_base = False
        res = brick_spring_simple(k, m, d0, start_cond, ts, vct)
    else:
        is_base = True
        res = res_d

    # Capture returned columns and select for plotting
    show_columns = []
    st.sidebar.write("Plot columns:")
    for c in res.columns:
        show_columns.append((c, st.sidebar.checkbox(c)))

    plot_cols = [_c[0] for _c in show_columns if _c[1]]

    st.write("### Simulation results:")

    if len(plot_cols) == 0:
        plot_cols = [_c[0] for _c in show_columns if _c[0].endswith("speed")]

    # grab selected columns in base results
    if not is_base:
        base_cols = [c for c in res_d for s in plot_cols if c.endswith(s)]
        full_plot_cols = base_cols + plot_cols
        fig = plot_brick_spring(pd.concat([res_d, res], axis=0), full_plot_cols)
        st.write("""
        The results are compared to the base parameters which are selected
        to mimic the *stiffness* of a *5wt rod*, *10m of 5wt* line
        and the a casting stroke used false casting this length of line:
        
        | Baseline           |  Baseline  |
        |---------           |------------|
        | Spring  constant: %0.01f [N/m]  | Brick mass: %0.01f [g]          | 
        | Car max speed: %0.01f [m/s]     | Car peak speed time: %0.02f [s] | 
        | Car stop time: %0.02f [s]       |                                 | 
        """ % (k_d, m_d * 1000.0, c_max_speed_d, c_turn_t_d, c_stop_t_d))
    else:
        fig = plot_brick_spring(res, plot_cols) # full_plot_cols)
    st.plotly_chart(fig)

    # Animation work in progress
    if show_simulation:
        font = ImageFont.truetype('./Open_Sans/OpenSans-Regular.ttf', 15)
        anim = BrickSpringAnim(res, font=font, cols=plot_cols, h=100, w=600)
        image = st.empty()
        st.write("""
        Animation may not work well due to bandwidth limitations.
        If this is the case: consider running it locally (see
        instructions on GitHub [https://github.com/grunde73/flycastsim](https://github.com/grunde73/flycastsim)).
        """)
        for _im in anim:
            image.image(_im)
            time.sleep(0.05)


elif topic[1] == 2:
    st.write("""
    # Placeholder for coming line model
    When the model for fly line flight is "ready"
    it will be displayed here.
    """)
