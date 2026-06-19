"""
Streamlit main app for FlyCasting simulator
"""
import pandas as pd
import streamlit as st

from flycastsim import brick_spring_simple, plot_brick_spring
from flycastsim import animate_brick_spring
from flycastsim import animate_fly_cast, plot_cast_snapshots
from flycastsim import plot_chord_comparison, load_cast1_frames
from flycastsim.fem import (simulate_cast1, CAST1_LINE_ETA,
                            CAST1_LINE_OUT)
from flycastsim.fem import _cast1_data



st.sidebar.title("Select section")
topic = st.sidebar.selectbox(
    "Select section",
    (("Introduction", 0), ("Simple 1D model", 1),
     ("Sample fly cast", 2)),
    format_func=lambda x: x[0],
    label_visibility="collapsed"
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
             1. A simple 1-D (brick-spring-car) model for casting
             1. A continuum (FEM) engine for a single beam/line, with an
                interactive *sample fly cast* demo

             #### The following is planned but not implemented:
             1. Air drag and material damping in the continuum engine
             1. Coupling of rod + line + leader + fly
             1. A full quantitative cast model

             The full sourcecode is available on GitHub
             [https://github.com/grunde73/flycastsim](https://github.com/grunde73/flycastsim).
             And updated documentation is found here:
             [https://grunde73.github.io/flycastsim/](https://grunde73.github.io/flycastsim/).
             
             
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
    show_base = st.sidebar.checkbox("Show reference case", value=True)
    mark_events = st.sidebar.checkbox("Mark key events", value=True)
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
    @st.cache_data
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
    if not is_base and show_base:
        base_cols = [c for c in res_d for s in plot_cols if c.endswith(s)]
        full_plot_cols = base_cols + plot_cols
        fig = plot_brick_spring(pd.concat([res_d, res], axis=0), full_plot_cols,
                                mark_events=mark_events)
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
        fig = plot_brick_spring(res, plot_cols, mark_events=mark_events)
    st.plotly_chart(fig)

    # Animation: rendered client-side with Plotly (smooth, scrubbable)
    if show_simulation:
        st.write("### Animation")
        anim_fig = animate_brick_spring(res)
        st.plotly_chart(anim_fig, width='stretch')


elif topic[1] == 2:
    st.write("""
    # Cast #1 — *The Rod & The Cast*
    Reproducing **Cast #1** from Løvoll & Borger's study
    *[The Rod & The Cast](https://www.sexyloops.com/articles/rodcast.shtml)*
    — the uploaded high-speed clip `cast01_m1` (caster: **Mathias
    Lilleheim**, **T&T Paradigm 9 ft 5-wt**, recorded at ~500 fps).

    The FEM rod is driven by the **rod-butt angle fitted to the footage**:
    the rod starts **up and back** and sweeps **clockwise** down toward the
    vertical as the loop forms — the tip stays elevated throughout.  The
    casting hand is also **hauled forward** (translated) as it rotates, and
    the full **~12.7 m line + leader** is modelled, **laid out behind** the
    caster at the start tilted ~5° below horizontal (line end lowest, rod
    tip highest) so the line **loads the rod**.  Pick the **AFTM line
    weight** in the sidebar (heavier line = more loading).  The simulated
    **rod chord length** (tip-to-handle distance) is compared against the
    measured curve.  Time
    is measured relative to **RSP** (Rod Straight Position, *t = 0*); the
    four event frames (MAV/MCL/RSP/MCF) all fall in the first ~0.69 s of
    real time (frames 243–346, RSP = frame 317), within the first 12 s of
    normal-speed playback.
    """)

    if show_intro:
        st.warning(
            "**What is and isn't matched.** Air drag can be toggled below, "
            "and the full ~12.7 m line + leader is modelled, laid out "
            "behind the caster at the start tilted ~5° below horizontal "
            "(line end lowest, rod tip highest). The AFTM line weight is "
            "adjustable (heavier line loads the rod more). A little "
            "line-only damping keeps that floppy layout stable while "
            "the rod stays elastic. The driving rod-butt motion is still an "
            "**idealized angle sweep fitted by eye** with a simple forward "
            "haul. Because the line is a single floppy subdomain (no "
            "leader/fly boundaries) it cannot unroll into a crisp loop — the "
            "heavy tilted line loads the rod deeply and the rod rebounds "
            "slightly after the stop. The match is therefore qualitative: the "
            "rod *geometry* (up-back start, clockwise loading sweep, tip "
            "elevated) and the loading/straightening of the chord, not exact "
            "magnitudes."
        )

    st.sidebar.write("## Rod & line (Cast #1)")
    line_weight = st.sidebar.select_slider(
        "Fly-line weight (AFTM)", options=[3, 4, 5, 6, 7, 8], value=5,
        help="Heavier lines carry more mass and load the rod more. "
             "5-wt matches the T&T Paradigm rig. The line mass profile is "
             "loaded from the bundled component data and scaled to this "
             "AFTM weight.")
    line_out = CAST1_LINE_OUT
    line_g = (_cast1_data.line_mass_per_length(line_weight)
              * line_out * 1000.0)
    head_g = _cast1_data.line_head_mass_grams(line_weight)
    st.sidebar.caption(
        f"AFTM {line_weight}-wt: **{head_g:.1f} g** per 30 ft head — "
        f"modelled line+leader ~**{line_g:.1f} g** over {line_out:.1f} m "
        f"(tapered profile from the component data files)")
    rod_ei_scale = st.sidebar.slider(
        "Rod stiffness scale", 0.5, 2.0, 1.0, 0.05,
        help="Multiplier on the data-driven rod bending-stiffness (EI) "
             "taper. 1.0 is the tabulated T&T Paradigm profile.")
    st.sidebar.write("## Numerics")
    n_nodes = st.sidebar.select_slider(
        "Grid nodes", options=[101, 121, 141], value=101,
        help="Total nodes split across rod/line/leader by length. The "
             "full-length floppy line needs a fairly fine grid "
             "(>= 101) to stay numerically stable.")
    air_drag = st.sidebar.checkbox("Air drag (Reynolds law)", value=False)
    damping_on = st.sidebar.checkbox("Material damping (Kelvin–Voigt)",
                                     value=False)
    show_snapshots = st.sidebar.checkbox("Show stroboscopic snapshots",
                                         value=True)

    run_clicked = st.sidebar.button("Run simulation", type="primary",
                                    width='stretch')

    params = (line_weight, rod_ei_scale, n_nodes, air_drag, damping_on)

    @st.cache_data(show_spinner="Simulating Cast #1...")
    def _run_cast1(line_weight, rod_ei_scale, n_nodes, air_drag,
                   damping_on):
        eta_rod = 2.5e-3 if damping_on else 0.0
        # The tilted-back line layout needs a little line damping to stay
        # stable; keep that floor and add a touch more when the user opts in.
        eta_line = max(CAST1_LINE_ETA, 1.0e-3 if damping_on else 0.0)
        return simulate_cast1(line_weight=line_weight,
                              rod_ei_scale=rod_ei_scale,
                              n_nodes=n_nodes, air_drag=air_drag,
                              eta_rod=eta_rod, eta_line=eta_line)

    # The simulator only runs when the user clicks **Run simulation** — not
    # on every parameter tweak.  Results (and the parameters they were run
    # with) are kept in session state so the page can re-render cheaply.
    if run_clicked:
        st.session_state["cast1_results"] = _run_cast1(*params)
        st.session_state["cast1_params"] = params

    # Event frames from the footage are always shown, run or not.
    st.write("### Real cast — event frames (from the footage)")
    frames = load_cast1_frames()
    if frames:
        cols = st.columns(len(frames))
        for col, (path, cap) in zip(cols, frames):
            col.image(path, caption=cap, width='stretch')
    else:
        st.info("Event frames not found (expected in `assets/cast1/`).")

    if "cast1_results" not in st.session_state:
        st.info("Set the rod, line and numerics parameters in the sidebar, "
                "then click **Run simulation** to simulate Cast #1.")
        st.stop()

    if st.session_state.get("cast1_params") != params:
        st.warning("Parameters changed since the last run — click **Run "
                   "simulation** to update the results below.")

    t_arr, X, Y, s_arr, chord, rod_tip = st.session_state["cast1_results"]

    st.write("### Simulated rod & line — upright camera view")
    st.plotly_chart(
        animate_fly_cast(t_arr, X, Y, rod_tip_index=rod_tip),
        width='stretch')

    if show_snapshots:
        st.write("### Rod & line shape through the stroke")
        st.plotly_chart(
            plot_cast_snapshots(t_arr, X, Y, rod_tip_index=rod_tip),
            width='stretch')

    st.write("### Chord length: simulated vs. measured")
    st.plotly_chart(plot_chord_comparison(t_arr, chord), width='stretch')
    st.caption(
        "Chord = straight-line distance from the rod handle to the rod "
        "tip. Measured curve and event markers (MAV/MCL/RSP/MCF) are from "
        "*The Rod & The Cast* (Table 1 / Figures 1–2). Source data under "
        "`data/sexyloops.com/`; video frames under `assets/cast1/`."
    )
