"""Streamlit views for fitted rod stiffness / mass profiles.

Used by ``streamlit_app.py`` (*Rod parameters* section).  All computation
lives in :mod:`flycastsim.rod`; this module only lays out widgets and plots.
Rods fitted in the app are kept for the session in
``st.session_state["session_rods"]`` (key -> fitted-rod folder) so the
comparison view and the Cast #1 rod selector can use them.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

from flycastsim.rod import (FIT_PRESETS, FittedRod, create_measurement,
                            export_fit, fit_rod,
                            fitted_rods_table, load_fitted_rods,
                            load_rod_measurement, plot_fitted_bend,
                            plot_fitted_frequency, plot_fitted_loads,
                            plot_fitted_profiles, trace_overlay)
from flycastsim.rod.archive import (extract_rod_archive, fitted_rod_zip,
                                    measurement_zip)


@st.cache_resource
def bundled_fitted_rods() -> dict[str, FittedRod]:
    """The fitted rods shipped with the package, by id."""
    return {rod.id: rod for rod in load_fitted_rods()}


def available_fitted_rods() -> dict[str, FittedRod]:
    """Bundled fitted rods plus rods fitted in this session.

    Keys are ``"bundled:<id>"`` and ``"session:<id>"``.
    """
    rods = {f"bundled:{k}": v for k, v in bundled_fitted_rods().items()}
    for key, folder in st.session_state.get("session_rods", {}).items():
        rods[key] = FittedRod.from_folder(folder)
    return rods


def rod_label(key: str, rod: FittedRod) -> str:
    """Display name of a fitted rod in selectors."""
    where = "fitted" if key.startswith("bundled:") else "fitted this session"
    return f"{rod.id} — {rod.label.removesuffix(' - fitted rod')} ({where})"


@st.cache_data(show_spinner="Rebuilding the fitted bend shapes...")
def _bend_figure(folder: str, every: int):
    return plot_fitted_bend(FittedRod.from_folder(folder), every=every)


def stiffness_profiles_page(show_intro: bool) -> None:
    """Compare fitted rods: profiles, fit to the data, summary table."""
    st.write("""
    # Rod parameters — Stiffness profiles
    Bending stiffness **EI(s)** and mass per length **μ(s)** along the rod,
    fitted to **static bend tests** (the rod clamped near the butt and
    loaded at the tip in steps, filmed frame by frame), a **tip-mass
    frequency test** and the **Common Cents System** (CCS) point.  The
    fitted rods can be used in *Sample fly cast* (Cast #1).
    """)
    if show_intro:
        st.info("""
        **How it works:** the rod centre line is traced in every frame of the
        bend test, and a large-deflection beam model (the *elastica*) is
        fitted to all frames at once, together with the frequency and CCS
        data.  EI is a smooth spline that may only decrease from butt to tip;
        the mass density is linear within each section (as for swingweight).
        The tip load of each frame, the give of the mount and the camera
        calibration are fitted too.  EI behind the clamp (the handle) is not
        observed and held constant; EI within ~0.3 m of the tip is poorly
        constrained, since the bending moment vanishes there.  See
        ``docs/rod_profile.rst`` for the details.
        """)

    rods = available_fitted_rods()
    if not rods:
        st.warning("No fitted rods found.")
        return
    keys = list(rods)
    chosen = st.multiselect(
        "Rods to compare", keys, default=keys,
        format_func=lambda k: rod_label(k, rods[k]))
    selected = [rods[k] for k in chosen]
    if not selected:
        st.info("Select at least one rod.")
        return

    st.plotly_chart(plot_fitted_profiles(selected), width="stretch")
    st.write("### Summary")
    st.dataframe(pd.DataFrame(fitted_rods_table(selected)).set_index("rod"),
                 width="stretch")
    st.caption(
        "Mass and swingweight come from the fitted mass profile (PA905 has "
        "no section measurements yet, so its mass profile is a guess). "
        "*CCS defl. model* is the model's tip deflection at the CCS load as "
        "a fraction of the free length (measured: 1/3).")

    col1, col2 = st.columns(2)
    col1.plotly_chart(plot_fitted_frequency(selected), width="stretch")
    col2.plotly_chart(plot_fitted_loads(selected), width="stretch")

    st.write("### Fit to the bend frames")
    key = st.selectbox("Rod", chosen,
                       format_func=lambda k: rod_label(k, rods[k]))
    every = st.slider("Show every n-th frame", 1, 4, 2)
    st.plotly_chart(_bend_figure(str(rods[key].folder), every),
                    width="stretch")
    st.caption(
        "Dots: traced rod centre line; x: tip; lines: the fitted model for "
        "each frame's fitted load, in image pixels (y down).")


# ---------------------------------------------------------------------------
# Upload & fit
# ---------------------------------------------------------------------------
#: Repository folder with the measured rods (not part of the installed
#: package; used to offer example data sets when available).
ASSETS = Path(__file__).resolve().parent / "assets"


def _session_root() -> Path:
    """Per-session scratch folder for uploads and fits."""
    if "rod_work_dir" not in st.session_state:
        st.session_state["rod_work_dir"] = tempfile.mkdtemp(
            prefix="flycastsim_rods_")
    return Path(st.session_state["rod_work_dir"])


@st.cache_data(show_spinner="Packing the example data set...")
def _example_zip(rod_id: str) -> bytes:
    return measurement_zip(load_rod_measurement(ASSETS / rod_id))


@st.cache_data(show_spinner="Tracing the rod in every frame...")
def _trace(folder: str, every: int, n_points: int):
    return load_rod_measurement(folder).extract_bend_frames(
        every=every, n_points=n_points)


def _measurement_overview(meas) -> None:
    """Show what was read from the uploaded rod.yaml."""
    ccs = meas.ccs_data()
    freq = meas.frequency_data()
    rows = {
        "rod": f"{meas.id} — {meas.label}",
        "length / clamp": f"{meas.length:.3f} m / {meas.clamp_s:.3f} m "
                          f"from the butt",
        "sections": (", ".join(f"{1e3 * s.mass:.1f} g" for s in meas.sections)
                     if meas.sections else "not measured (generic guess)"),
        "bend frames": f"{len(meas.frame_paths())}, excluded: "
                       f"{meas.raw['static_bend'].get('exclude_frames') or '-'}",
        "CCS": (f"IP {1e3 * ccs.ip_mass:.0f} g at "
                f"{ccs.deflection_fraction:.3f} of the free length"
                if ccs else "-"),
        "frequency test": (f"{len(freq.tip_masses)} tip masses up to "
                           f"{1e3 * max(freq.tip_masses):.0f} g"
                           if freq else "-"),
    }
    st.table(pd.DataFrame(rows.items(), columns=["", "value"])
             .set_index(""))


def _register_fit(meas, result, preset: str) -> FittedRod:
    """Export a fit into the session folder and make it available to the
    comparison view and Cast #1."""
    rods = st.session_state.setdefault("session_rods", {})
    n = sum(k.startswith(f"session:{meas.id}") for k in rods)
    rod_id = meas.id if n == 0 else f"{meas.id}-{n + 1}"
    folder = _session_root() / "fits" / rod_id
    notes = [f"{meas.id} ({meas.label}): fitted in the flycastsim app",
             f"preset {preset}"]
    export_fit(meas, result, folder, notes=notes, preset=preset)
    summary_path = folder / "fit_summary.json"
    summary = json.loads(summary_path.read_text())
    summary["rod"] = rod_id
    summary_path.write_text(json.dumps(summary, indent=1) + "\n")
    rods[f"session:{rod_id}"] = str(folder)
    return FittedRod.from_folder(folder)


def _fit_results(rod: FittedRod) -> None:
    """Show a freshly fitted rod next to the bundled rods."""
    st.success(f"Fitted **{rod.id}** — now available in *Stiffness "
               "profiles* and in the Cast #1 rod selector for this session.")
    others = list(bundled_fitted_rods().values())
    st.plotly_chart(plot_fitted_profiles([rod] + others), width="stretch")
    st.dataframe(pd.DataFrame(fitted_rods_table([rod])).set_index("rod"),
                 width="stretch")
    col1, col2 = st.columns(2)
    col1.plotly_chart(plot_fitted_frequency([rod]), width="stretch")
    col2.plotly_chart(plot_fitted_loads([rod]), width="stretch")
    st.plotly_chart(plot_fitted_bend(rod, every=2), width="stretch")
    st.download_button(
        "Download fitted rod (zip)", fitted_rod_zip(rod.folder, rod.id),
        file_name=f"{rod.id}_fitted_rod.zip", mime="application/zip",
        help="rod.json + rod.csv (FEM component, loadable with "
             "flycastsim.fem.components.load_component), fit_summary.json "
             "and the rod.yaml it was fitted from.")


def _fit_section(folder: Path) -> None:
    """Trace preview, fit button and results for a measurement folder."""
    try:
        meas = load_rod_measurement(folder)
    except Exception as exc:          # show any config problem to the user
        st.error(f"Could not read rod.yaml: {exc}")
        return
    _measurement_overview(meas)

    preset = st.radio(
        "Fit settings", ["quick", "full"], horizontal=True,
        format_func=lambda p: {"quick": "Quick (~1–3 min)",
                               "full": "Full (~3–10 min)"}[p],
        help="Quick uses every 3rd frame, fewer points and coefficients and "
             "looser tolerances; Full is what the bundled rods were fitted "
             "with.")
    settings = FIT_PRESETS[preset]

    st.write("#### 1. Check the tracing")
    try:
        frames, scale = _trace(str(folder), settings["every"],
                               settings["n_points"])
    except Exception as exc:
        st.error(f"Tracing failed: {exc}. Check `calibration.clamp_px` and "
                 "`static_bend.trace_start_px` in rod.yaml.")
        return
    paths = meas.frame_paths()
    last = paths[int(max(f.load_steps for f in frames))]
    st.image(trace_overlay(last, frames,
                           clamp_px=meas.raw["calibration"].get("clamp_px"),
                           start_px=meas.raw["static_bend"].get(
                               "trace_start_px")),
             caption=f"{len(frames)} traced frames on the most loaded one "
                     "(red circle: clamp, green circle: trace start, "
                     "x: tips used). Pixel scale from the rod length: "
                     f"{scale * 1e3:.3f} mm/px.", width="stretch")
    dropped = sum(f.tip is None for f in frames)
    if dropped:
        st.caption(f"{dropped} traced tip(s) disagreed with the constant "
                   "rod length and are not used.")

    st.write("#### 2. Fit")
    key = (str(folder), preset)
    if st.button("Fit stiffness and mass profiles", type="primary"):
        with st.status("Fitting...", expanded=True) as status:
            line = st.empty()

            def progress(n, cost):
                line.write(f"model evaluations: {n}, cost: {cost:,.1f}")

            result = fit_rod(meas, preset, frames=frames, scale=scale,
                             progress=progress)
            rod = _register_fit(meas, result, preset)
            st.session_state.setdefault("upload_fits", {})[key] = \
                str(rod.folder)
            status.update(label=f"Fit done: {result.optimize.nfev} "
                                f"evaluations, cost "
                                f"{result.optimize.cost:,.1f} for "
                                f"{result.optimize.fun.size} residuals",
                          state="complete", expanded=False)
    fitted = st.session_state.get("upload_fits", {}).get(key)
    if fitted:
        _fit_results(FittedRod.from_folder(fitted))


def upload_fit_page(show_intro: bool) -> None:
    """Upload a measured rod (zip) and fit its stiffness and mass."""
    st.write("""
    # Rod parameters — Upload & fit
    Fit the stiffness and mass profiles of your own rod from a static bend
    test, a tip-mass frequency test and (optionally) the CCS point and
    section masses.
    """)
    if show_intro:
        st.info("""
        **Guided form:** enter the rod data, CCS and frequency test, upload
        the bend-test frames and click on a frame to place the clamp and the
        trace start.

        **Zip of a rod folder:** a ``rod.yaml`` (the measurement
        description, see ``assets/PA905/rod.yaml`` for an annotated example)
        with the bend-test frames, the frequency CSV (``m[g],f[hz]``) and,
        for raw photos, a background frame without the rod.  Paths in
        ``rod.yaml`` are relative to its folder.  The frames must show the
        rod clamped about 25 cm from the butt, loaded at the tip in steps,
        with the clamp point and a trace start (just outboard of the mount)
        given in pixels.  The fitted rod can be downloaded and is available
        for the rest of the session in *Stiffness profiles* and *Sample fly
        cast*.
        """)

    mode = st.radio("Input", ["zip", "form"], horizontal=True,
                    format_func=lambda m: {"zip": "Zip of a rod folder",
                                           "form": "Guided form"}[m])
    if mode == "form":
        guided_form_page()
        return

    examples = sorted(p.parent.name for p in ASSETS.glob("*/rod.yaml"))
    if examples:
        col1, col2 = st.columns([2, 1])
        example = col1.selectbox(
            "Example data sets (the bundled rods' measurements)", examples,
            index=examples.index("XP590") if "XP590" in examples else 0)
        col2.write("")
        col2.download_button("Download example zip", _example_zip(example),
                             file_name=f"{example}_measurement.zip",
                             mime="application/zip")

    upload = st.file_uploader("Rod data set (zip)", type="zip")
    if upload is None:
        return
    data = upload.getvalue()
    digest = hashlib.sha1(data).hexdigest()[:12]
    target = _session_root() / "uploads" / digest
    folder_key = f"upload_folder_{digest}"
    if folder_key not in st.session_state:
        try:
            st.session_state[folder_key] = str(extract_rod_archive(data,
                                                                   target))
        except (ValueError, zipfile.BadZipFile) as exc:
            st.error(f"Could not use the archive: {exc}")
            return
    _fit_section(Path(st.session_state[folder_key]))


# ---------------------------------------------------------------------------
# Guided form
# ---------------------------------------------------------------------------
_OVERVIEW_WIDTH = 1200        # px, overview image sent to the browser
_ZOOM_HALF = 120              # px of the frame around a point in the zoom


def _marked(img, points: dict, box=None):
    """Copy of ``img`` with the clamp (red) and trace start (green) marked;
    ``box`` = ``(x0, y0)`` offset when ``img`` is a crop."""
    from PIL import ImageDraw

    out = img.convert("RGB")
    draw = ImageDraw.Draw(out)
    x0, y0 = box or (0, 0)
    r = max(4, out.width // 150)
    for name, color in (("clamp", "#FF0000"), ("start", "#00FF00")):
        if name in points:
            x, y = points[name][0] - x0, points[name][1] - y0
            draw.ellipse([x - r, y - r, x + r, y + r], outline=color,
                         width=max(2, r // 3))
            draw.line([x - 2 * r, y, x + 2 * r, y], fill=color, width=1)
            draw.line([x, y - 2 * r, x, y + 2 * r], fill=color, width=1)
    return out


def _point_picker(image_bytes: bytes) -> dict:
    """Click to place the clamp point and the trace start on a frame.

    Returns ``{"clamp": (x, y), "start": (x, y)}`` in frame pixels (keys
    present once placed).  A click on the overview places the selected point
    roughly; a click on the zoomed crop around it refines it.
    """
    import io

    from PIL import Image
    from streamlit_image_coordinates import streamlit_image_coordinates

    points = st.session_state.setdefault("form_points", {})
    img = Image.open(io.BytesIO(image_bytes))
    target = st.radio(
        "Click to place", ["clamp", "start"], horizontal=True,
        format_func=lambda k: {"clamp": "Clamp point (red) — where the rod "
                                        "leaves the front of the mount",
                               "start": "Trace start (green) — on the rod, "
                                        "a few cm outboard of the mount"}[k])
    overview = _marked(img, points)
    if overview.width > _OVERVIEW_WIDTH:
        overview = overview.resize(
            (_OVERVIEW_WIDTH,
             round(overview.height * _OVERVIEW_WIDTH / overview.width)))
    # shown at the column width: convert clicks with the displayed width
    click = streamlit_image_coordinates(overview, width="stretch",
                                        image_format="JPEG",
                                        key="form_overview")
    if click and click != st.session_state.get("form_last_overview"):
        st.session_state["form_last_overview"] = click
        scale = img.width / click["width"]
        points[target] = (round(click["x"] * scale), round(click["y"] * scale))
        st.rerun()

    if target in points:
        x, y = points[target]
        x0 = int(min(max(x - _ZOOM_HALF, 0), img.width - 2 * _ZOOM_HALF))
        y0 = int(min(max(y - _ZOOM_HALF, 0), img.height - 2 * _ZOOM_HALF))
        crop = img.crop((x0, y0, x0 + 2 * _ZOOM_HALF, y0 + 2 * _ZOOM_HALF))
        zoom = 2           # crop shown at twice its pixel size (at most)
        st.caption("Zoom around the selected point — click to refine.")
        fine = streamlit_image_coordinates(
            _marked(crop, points, box=(x0, y0)).resize(
                (crop.width * zoom, crop.height * zoom)),
            width="content", key=f"form_zoom_{target}")
        if fine and fine != st.session_state.get(f"form_last_zoom_{target}"):
            st.session_state[f"form_last_zoom_{target}"] = fine
            scale = crop.width / fine["width"]      # crop px per display px
            points[target] = (x0 + round(fine["x"] * scale),
                              y0 + round(fine["y"] * scale))
            st.rerun()
    st.write("Clamp: " + (f"{points['clamp']}" if "clamp" in points
                          else "not set") +
             " · trace start: " + (f"{points['start']}" if "start" in points
                                   else "not set") + " (pixels)")
    return points


def guided_form_page() -> None:
    """Enter a rod's measurements in a form, upload its frames, place the
    clamp and trace start, and fit."""
    st.write("#### Rod")
    c1, c2, c3 = st.columns(3)
    rod_id = c1.text_input("Short id", "MYROD",
                           help="Used to name the fitted rod.")
    make = c2.text_input("Make", "")
    model = c3.text_input("Model", "")
    c1, c2 = st.columns(2)
    length = c1.number_input("Assembled length [m]", 1.5, 4.5, 2.743, 0.001,
                             format="%.3f")
    clamp_s = c2.number_input(
        "Clamp position from the butt [m]", 0.0, 1.0, 0.25, 0.01,
        help="Distance from the butt to where the rod leaves the front of "
             "the mount in the bend test.")

    sections = None
    if st.checkbox("I have section masses and balance points",
                   help="Weighed sections and their balance points (from the "
                        "thick end) pin down the mass profile; without them "
                        "a generic guess is used."):
        n = int(st.number_input("Number of sections", 2, 6, 4))
        default = pd.DataFrame({
            "name": ["butt"] + [f"section {i}" for i in range(2, n)]
            + ["tip"],
            "mass_g": [None] * n, "length_m": [None] * n,
            "mass_center_m": [None] * n})
        table = st.data_editor(default, num_rows="fixed", hide_index=True,
                               key=f"form_sections_{n}")
        if table[["mass_g", "length_m", "mass_center_m"]].notna().all().all():
            sections = table.to_dict("records")
        else:
            st.caption("Fill in all cells to use the section data.")

    st.write("#### Common Cents System (optional)")
    c1, c2, c3 = st.columns(3)
    ip = c1.number_input("IP [g] (0 = not measured)", 0.0, 1000.0, 0.0, 1.0)
    fraction = c2.number_input("Deflection fraction", 0.1, 0.6, 1 / 3, 0.01,
                               format="%.4f")
    aa = c3.number_input("Action angle [deg] (0 = not measured)", 0.0, 90.0,
                         0.0, 1.0)

    st.write("#### Tip-mass frequency test (optional, recommended)")
    st.caption("Clamp the rod as in the bend test, add a tip mass, and "
               "measure the lowest bending frequency.  This sets the "
               "absolute scale of stiffness and mass.")
    freq = st.data_editor(pd.DataFrame({"tip mass [g]": [0.0, 4.0, 8.0],
                                        "frequency [Hz]": [None] * 3}),
                          num_rows="dynamic", hide_index=True,
                          key="form_frequency")
    freq = freq.dropna()
    frequency = list(freq.itertuples(index=False, name=None)) or None

    st.write("#### Static bend frames")
    files = st.file_uploader(
        "Frames in load order (sorted by file name; the first with no added "
        "load)", type=["jpg", "jpeg", "png", "tif", "tiff"],
        accept_multiple_files=True)
    background = st.file_uploader(
        "Background frame without the rod (raw photos only)",
        type=["jpg", "jpeg", "png", "tif", "tiff"])
    if not files:
        if not frequency and not ip:
            st.warning("Without the frequency test or the CCS load the "
                       "absolute stiffness cannot be determined.")
        return
    files = sorted(files, key=lambda f: f.name)
    exclude = st.multiselect(
        "Frames to leave out of the fit", list(range(len(files))),
        default=[0],
        format_func=lambda k: f"{k}: {files[k].name}",
        help="The unloaded frame 0 is left out by default: on all bundled "
             "rods it sagged more than the loaded frames allow (likely the "
             "mount).  Also leave out frames where the tip leaves the "
             "image.")

    st.write("#### Clamp point and trace start")
    points = _point_picker(files[-1].getvalue())
    if not {"clamp", "start"} <= set(points):
        st.info("Place both points to continue.")
        return

    if st.button("Build data set and preview tracing"):
        # every input goes into the folder name, so changed inputs never
        # reuse a stale trace or fit
        inputs = (rod_id, make, model, length, clamp_s, sections, ip,
                  fraction, aa, frequency, exclude, sorted(points.items()),
                  [(f.name, f.size) for f in files],
                  (background.name, background.size) if background else None)
        folder = _session_root() / "forms" / hashlib.sha1(
            repr(inputs).encode()).hexdigest()[:12]
        create_measurement(
            folder, rod_id=rod_id or "MYROD", make=make, model=model,
            length=length, clamp_s=clamp_s,
            frames=[(f.name, f.getvalue()) for f in files],
            clamp_px=points["clamp"], trace_start_px=points["start"],
            exclude_frames=exclude,
            background=((background.name, background.getvalue())
                        if background else None),
            sections=sections, ccs_ip_g=ip or None, ccs_fraction=fraction,
            action_angle_deg=aa or None, frequency=frequency)
        st.session_state["form_folder"] = str(folder)
    if "form_folder" in st.session_state:
        _fit_section(Path(st.session_state["form_folder"]))
