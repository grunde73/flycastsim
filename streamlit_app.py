"""
Streamlit main app for FlyCasting simulator
"""
import pandas as pd
import streamlit as st

from flycastsim import brick_spring_simple, plot_brick_spring
from flycastsim import animate_brick_spring
from flycastsim import animate_fly_cast, plot_cast_snapshots
from flycastsim import plot_chord_comparison, plot_tip_deflection
from flycastsim import plot_cast_speeds
from flycastsim import load_cast1_frames
from flycastsim.fem import (simulate_cast1, CAST1_LINE_ETA,
                            CAST1_LINE_OUT, CAST1_ROD_LENGTH)
from flycastsim.fem import (node_speed, node_index_from_tip,
                            rigid_lever_speed)
from flycastsim.fem import _cast1_data
from flycastsim import RodSection, plot_swingweight_contributions
from flycastsim import swingweight as estimate_swingweight
from flycastsim.rod import load_example_rods



st.sidebar.title("Select section")
topic = st.sidebar.selectbox(
    "Select section",
    (("Introduction", 0), ("Simple 1D model", 1),
     ("Sample fly cast", 2), ("Rod parameters", 3)),
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
             1. A continuum (FEM) engine for a coupled rod + line, with an
                interactive *sample fly cast* demo reproducing **Cast #1**
                from *The Rod & The Cast*
             1. Optional **air drag** (Reynolds law) and **material
                damping** (Kelvin–Voigt) in the continuum engine
             1. A **rod parameters** tool that estimates a rod's
                *swingweight* (butt-axis moment of inertia)

             #### The following is planned but not fully implemented:
             1. Distinct leader + fly subdomains so the line can unroll
                into a crisp loop
             1. A full quantitative cast model with tuned parameters, validated against high-speed footage
             1. A design tool to explore the effect of different rod tapers and line profiles

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
    **rod chord length** (tip to a base point ~30 cm up the rod blank) is
    compared against the
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
    show_rigid_rod = st.sidebar.checkbox("Show imaginary rigid rod",
                                         value=False)
    line_speed_dist = st.sidebar.slider(
        "Line speed point — distance from line tip [m]",
        0.0, float(round(CAST1_LINE_OUT, 1)), 0.0, 0.5,
        help="Where to measure line speed: arc-length distance back from the "
             "line/leader tip (0 = the fly tip). Display-only — changing it "
             "re-reads the last run, no re-simulation needed.")

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

    t_arr, X, Y, s_arr, chord, deflection, deflection_vec, rod_tip = \
        st.session_state["cast1_results"]

    st.write("### Simulated rod & line — upright camera view")
    if show_rigid_rod:
        butt_angle = _cast1_data.phi_handle_rad(t_arr)
        cast_anim = animate_fly_cast(t_arr, X, Y, rod_tip_index=rod_tip,
                                     rigid_rod_angle=butt_angle,
                                     rigid_rod_length=CAST1_ROD_LENGTH)
    else:
        cast_anim = animate_fly_cast(t_arr, X, Y, rod_tip_index=rod_tip)
    # Streamlit's fullscreen ("expand") view re-mounts the chart from cached
    # figure state and loses Plotly's named animation frames, so Play/slider
    # stop working there.  Hide the fullscreen button for this animated chart
    # (other, static charts keep theirs) and keep the inline view large.
    st.markdown(
        "<style>.st-key-cast1_animation "
        "[data-testid='stElementToolbar']{display:none;}</style>",
        unsafe_allow_html=True)
    with st.container(key="cast1_animation"):
        st.plotly_chart(cast_anim, width='stretch')
    if show_rigid_rod:
        st.caption(
            "Dashed line = the imaginary **rigid (undeflected) rod**: a "
            "straight rod from the handle along the rod-butt tangent. The gap "
            "between the real rod tip and this dashed rod's tip is what the "
            "tip-deflection plot below measures."
        )

    st.write("### Rod tip deflection")
    st.plotly_chart(plot_tip_deflection(t_arr, deflection), width='stretch')
    st.caption(
        "Tip deflection = signed perpendicular distance from the rod tip to "
        "the undeflected (straight) rod — the tangent line through the handle. "
        "Positive = tip on the counter-clockwise side of the butt-tangent "
        "direction; 0 = straight rod. Simulated-only (no measured curve); "
        "event markers (MAV/MCL/RSP/MCF) marked."
    )

    st.write("### Rod, line & rigid-lever speed")
    butt_angle_speed = _cast1_data.phi_handle_rad(t_arr)
    rod_tip_speed = node_speed(t_arr, X, Y, rod_tip)
    line_idx = node_index_from_tip(s_arr, line_speed_dist,
                                   start=rod_tip, stop=X.shape[1])
    line_speed = node_speed(t_arr, X, Y, line_idx)
    lever_speed = rigid_lever_speed(t_arr, X, Y, butt_angle_speed,
                                    CAST1_ROD_LENGTH)
    st.plotly_chart(
        plot_cast_speeds(t_arr, rod_tip_speed, line_speed, lever_speed,
                         line_distance=line_speed_dist),
        width='stretch')
    st.caption(
        "Speeds differentiate the simulated node positions over time. "
        "**Rod tip** = the real (deflected) rod tip; **rigid lever** = the tip "
        "of the imaginary straight (undeflected) rod swung about the handle, "
        "i.e. the tip speed with zero rod flex — the gap to the rod-tip curve "
        "is the speed the rod's bend-and-unbend adds. **Line** = a line node "
        f"{line_speed_dist:.1f} m back from the line tip (set in the sidebar). "
        "The ✕ markers are the exact published rod-tip speeds (Table 1); event "
        "markers (MAV/MCL/RSP/MCF) are shown."
    )

    if show_snapshots:
        st.write("### Rod & line shape through the stroke")
        st.plotly_chart(
            plot_cast_snapshots(t_arr, X, Y, rod_tip_index=rod_tip),
            width='stretch')

    st.write("### Chord length: simulated vs. measured")
    st.plotly_chart(plot_chord_comparison(t_arr, chord), width='stretch')
    st.caption(
        "Chord = straight-line distance from the rod tip to a base point "
        "~30 cm up the rod blank. Measured curve and event markers "
        "(MAV/MCL/RSP/MCF) are from "
        "*The Rod & The Cast* (Table 1 / Figures 1–2). Source data under "
        "`data/sexyloops.com/`; video frames under `assets/cast1/`."
    )


elif topic[1] == 3:
    st.write("""
    # Rod parameters — Swingweight
    Estimate a fly rod's **swingweight**: the moment of inertia (MOI) of the
    rod about an axis at the **butt**.  Swingweight captures how a rod *feels*
    to swing far better than its bare mass — mass out towards the tip counts
    much more than mass near the grip, because MOI grows with the **square** of
    the distance to the axis.

    The estimate uses the method from Løvoll & Angus,
    *Measuring fly rod "swingweight"* (2008) — bundled under
    [`data/swingweight.pdf`](https://www.sexyloops.com/articles/swingweight.pdf).
    It assumes the mass density of each section falls off linearly from the
    thick end, accounts for the **ferrule overlap**, and applies a dedicated
    **reel-seat / grip** correction to the butt section of finished rods.
    """)

    if show_intro:
        st.info("""
        **What you measure (per section, butt → tip):**

        1. the **section length**,
        1. the **section mass**, and
        1. the **balance point** — the distance from the *thick (butt) end* of
           that section to where it balances on a hard edge.

        Also measure the **total assembled length** of the rod (used to work
        out the ferrule overlap).  Use scales with ~0.1 g resolution and
        measure lengths to ~1 mm: the paper notes the swingweight estimate is
        good to about **±1 g·m²**.
        """)

    examples = load_example_rods()
    example_labels = ["— custom (enter your own) —"] + [r.label for r in examples]

    st.sidebar.write("## Rod measurements")
    preset = st.sidebar.selectbox(
        "Start from", example_labels,
        help="Load one of the worked-example rods from the paper, or enter "
             "your own measurements in the table.")
    has_reel_seat = st.sidebar.checkbox(
        "Finished rod (reel seat + grip)", value=True,
        help="Tick for a built rod so the heavy reel seat and grip at the "
             "butt are corrected for. Untick for a bare blank.")

    is_custom = preset == example_labels[0]

    # Number of sections selector — custom data only (presets define their own
    # section count).
    if is_custom:
        n_sections = int(st.sidebar.number_input(
            "Number of sections", min_value=1, max_value=8, value=4, step=1,
            help="How many sections (pieces) your rod has, butt to tip."))
    else:
        n_sections = len(examples[example_labels.index(preset) - 1].sections)

    def _section_label(i, n):
        if i == 0:
            return "butt"
        if i == n - 1:
            return "tip"
        return f"section {i + 1}"

    def _rows_from_example(rod):
        return [
            {"Section": s.name or _section_label(i, len(rod.sections)),
             "Mass [g]": round(s.mass * 1000.0, 2),
             "Length [m]": s.length,
             "Balance point [m]": s.mass_center}
            for i, s in enumerate(rod.sections)
        ]

    # Per-position defaults used to seed / grow the custom table.
    _custom_defaults = [
        {"Mass [g]": 60.0, "Length [m]": 0.72, "Balance point [m]": 0.16},
        {"Mass [g]": 16.0, "Length [m]": 0.72, "Balance point [m]": 0.31},
        {"Mass [g]": 8.0, "Length [m]": 0.72, "Balance point [m]": 0.32},
        {"Mass [g]": 4.0, "Length [m]": 0.72, "Balance point [m]": 0.33},
    ]

    def _custom_rows(n, existing=None):
        """Build exactly ``n`` custom rows, keeping existing values by index."""
        rows = []
        existing = existing if existing is not None else []
        for i in range(n):
            if i < len(existing):
                vals = dict(existing[i])
            elif i < len(_custom_defaults):
                vals = dict(_custom_defaults[i])
            else:
                vals = {"Mass [g]": 3.0, "Length [m]": 0.72,
                        "Balance point [m]": 0.33}
            vals["Section"] = _section_label(i, n)
            rows.append({"Section": vals["Section"],
                         "Mass [g]": vals["Mass [g]"],
                         "Length [m]": vals["Length [m]"],
                         "Balance point [m]": vals["Balance point [m]"]})
        return rows

    # Seed / rebuild the editable table when the preset changes, or (for custom
    # data) when the section count changes — preserving entered values on resize.
    preset_changed = st.session_state.get("sw_preset") != preset
    count_changed = (is_custom
                     and st.session_state.get("sw_n_sections") != n_sections)
    if preset_changed or count_changed:
        st.session_state["sw_preset"] = preset
        st.session_state["sw_n_sections"] = n_sections
        if is_custom:
            prev = st.session_state.get("sw_rows")
            existing = prev.to_dict("records") if prev is not None else None
            st.session_state["sw_rows"] = pd.DataFrame(
                _custom_rows(n_sections, existing))
            if preset_changed:
                st.session_state["sw_assembled"] = 2.73
                st.session_state["sw_reel"] = True
        else:
            rod = examples[example_labels.index(preset) - 1]
            st.session_state["sw_rows"] = pd.DataFrame(_rows_from_example(rod))
            st.session_state["sw_assembled"] = float(rod.assembled_length)
            st.session_state["sw_reel"] = bool(rod.has_reel_seat)

    assembled_length = st.sidebar.number_input(
        "Assembled rod length [m]", min_value=0.5, max_value=6.0,
        value=float(st.session_state.get("sw_assembled", 2.73)), step=0.01,
        format="%.3f",
        help="Length of the fully assembled rod. The sum of the section "
             "lengths above will normally exceed this by the ferrule overlap.")

    st.write("### Section measurements (butt → tip)")
    st.caption("Set the **number of sections** in the sidebar (for custom "
               "data), then fill in each row. *Balance point* is measured from "
               "the thick (butt) end of each section.")
    # Shape-dependent key so the editor remounts when the row count changes,
    # avoiding stale per-cell edit state from a different section count.
    _editor_key = f"sw_editor_{is_custom}_{n_sections}"
    edited = st.data_editor(
        st.session_state["sw_rows"], num_rows="fixed",
        width='stretch', key=_editor_key,
        column_config={
            "Section": st.column_config.TextColumn("Section", disabled=True),
            "Mass [g]": st.column_config.NumberColumn(
                "Mass [g]", min_value=0.0, step=0.1, format="%.2f"),
            "Length [m]": st.column_config.NumberColumn(
                "Length [m]", min_value=0.0, step=0.01, format="%.3f"),
            "Balance point [m]": st.column_config.NumberColumn(
                "Balance point [m]", min_value=0.0, step=0.01, format="%.3f"),
        })
    # Persist the latest values so they survive a section-count resize.
    st.session_state["sw_rows"] = edited.copy()

    # Build RodSection list from the (possibly edited) table.
    rows = edited.dropna(subset=["Mass [g]", "Length [m]", "Balance point [m]"])
    sections = []
    for i, row in rows.reset_index(drop=True).iterrows():
        length = float(row["Length [m]"])
        x_cm = float(row["Balance point [m]"])
        mass_g = float(row["Mass [g]"])
        name = str(row["Section"]) if str(row["Section"]).strip() else \
            f"section {i + 1}"
        if length <= 0 or mass_g <= 0:
            continue
        sections.append(RodSection.from_grams(mass_g, length, x_cm, name=name))

    if len(sections) == 0:
        st.info("Enter at least one rod section above to estimate the "
                "swingweight.")
        st.stop()

    if has_reel_seat and len(sections) < 2:
        st.warning("The reel-seat / grip correction needs at least two "
                   "sections (the butt blank balance point is inferred from "
                   "the section above). Showing the bare-blank estimate "
                   "instead — untick *Finished rod* to silence this notice.")
        use_reel_seat = False
    else:
        use_reel_seat = has_reel_seat

    # The linear-density model is only valid for a section's balance point in
    # [l/3, 2l/3]. Skip the butt section when the reel-seat correction is on:
    # its measured balance point is deliberately distorted by the reel seat
    # and is not used directly (the blank balance point is inferred instead).
    for i, sec in enumerate(sections):
        if use_reel_seat and i == 0:
            continue
        lo, hi = sec.length / 3.0, 2.0 * sec.length / 3.0
        if not (lo - 1e-9 <= sec.mass_center <= hi + 1e-9):
            st.warning(
                f"**{sec.name}**: balance point {sec.mass_center:.3f} m is "
                f"outside the valid range [{lo:.3f}, {hi:.3f}] m (l/3 … 2l/3) "
                f"for the linear-density model — the estimate may be "
                f"unreliable.")

    result = estimate_swingweight(sections, assembled_length,
                                  has_reel_seat=use_reel_seat)

    st.write("### Result")
    c1, c2 = st.columns(2)
    c1.metric("Swingweight  Iₛ", f"{result.swingweight_gm2:.1f} g·m²")
    c2.metric("Total rod mass",
              f"{sum(s.mass for s in sections) * 1000.0:.1f} g")
    st.caption("Think of the swingweight as the mass you'd feel if it were "
               "stuck on the tip of an imaginary 1 m long massless stick.")

    st.plotly_chart(plot_swingweight_contributions(result), width='stretch')

    st.write("### Per-section breakdown")
    breakdown = pd.DataFrame([
        {"Section": s.name,
         "Mass [g]": s.mass * 1000.0,
         "Length [m]": s.length,
         "Balance pt [m]": s.mass_center,
         "Dist. to butt d [m]": s.d,
         "MOI [g·m²]": s.I_sec_gm2,
         "Share [%]": (100.0 * s.I_sec / result.swingweight
                       if result.swingweight else 0.0)}
        for s in result.sections
    ])
    st.dataframe(
        breakdown.style.format({
            "Mass [g]": "{:.2f}", "Length [m]": "{:.3f}",
            "Balance pt [m]": "{:.3f}", "Dist. to butt d [m]": "{:.3f}",
            "MOI [g·m²]": "{:.2f}", "Share [%]": "{:.1f}"}),
        width='stretch', hide_index=True)

    if result.n_ferrules > 0:
        st.caption(
            f"Estimated ferrule overlap: **{result.ferrule_overlap * 1000:.1f} "
            f"mm** per ferrule ({result.n_ferrules} ferrules; section lengths "
            f"sum to {result.sum_section_length:.3f} m vs. "
            f"{result.assembled_length:.3f} m assembled).")

    if result.reel_seat_grip is not None:
        rsg = result.reel_seat_grip
        st.caption(
            f"Reel-seat / grip correction: modelled as a {rsg.length * 100:.0f} "
            f"cm uniform cylinder of **{rsg.mass * 1000:.1f} g**, leaving a "
            f"**{rsg.blank_mass * 1000:.1f} g** butt blank with inferred "
            f"balance point {rsg.x_bcm:.3f} m from the butt.")
