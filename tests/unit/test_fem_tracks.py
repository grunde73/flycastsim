"""Strokes from tracked points (``stroke-extraction`` spec)."""
import dataclasses
import json
import warnings

import numpy as np
import pytest

from flycastsim.fem import (
    Stroke,
    StrokeExtraction,
    StrokeTracks,
    load_stroke,
    load_tracks,
    save_stroke,
    save_tracks,
    stroke_from_tracks,
    tracks_from_stroke,
)

FPS = 240.0
SCALE = 0.003          # m per pixel
ROD_POINT = 0.40       # m between the two points

# Short hand-made tracks start and end in motion; that warning is tested on
# its own below.
pytestmark = pytest.mark.filterwarnings(
    "ignore:tracks .* the track (starts|ends) while:UserWarning")


@pytest.fixture(scope="module")
def cast1():
    return load_stroke("cast1")


def _truth(cast1, t):
    """Cast #1 angle [deg] and hand path relative to RSP [m] at ``t``."""
    hx, hy = cast1.hand_xy(t)
    x0, y0 = cast1.hand_xy(0.0)
    return np.rad2deg(cast1.angle(t)), hx - x0, hy - y0


def _manual_tracks(angle_deg, *, rsp_row=None, **kwargs):
    """Tracks in metres, ``y`` up, with the rod in known directions."""
    a = np.deg2rad(np.asarray(angle_deg, dtype=float))
    n = a.size
    t = np.arange(n) / 100.0
    butt = np.column_stack([0.01 * np.arange(n), np.zeros(n)])
    rod = butt + ROD_POINT * np.column_stack([np.cos(a), np.sin(a)])
    rsp_row = n - 1 if rsp_row is None else rsp_row
    kwargs = {"units": "m"} | kwargs
    return StrokeTracks(name="manual", t=t, butt=butt, rod=rod,
                        rsp_t=float(t[rsp_row]), **kwargs)


SPEC = {"name": "file tracks", "kind": "stroke_tracks",
        "table_csv": "tracks.csv",
        "columns": {"frame": "frame", "butt_x": "bx", "butt_y": "by",
                    "rod_x": "rx", "rod_y": "ry"},
        "fps": 100, "units": "px", "scale": {"m_per_px": 0.004},
        "rsp": {"frame": 6}, "butt_offset_m": 0.05, "tracking_noise": 1.5,
        "description": "from a file", "source": {"camera": "phone"}}
HEADER = ["frame", "bx", "by", "rx", "ry"]


def _rows(n=10):
    """``n`` rows with the rod sweeping forward, in pixels with ``y`` down."""
    out = []
    for i in range(n):
        a = np.deg2rad(120.0 - 8.0 * i)
        bx, by = 500.0 + 3.0 * i, 400.0
        out.append([i, bx, by, round(bx + 100.0 * np.cos(a), 3),
                    round(by - 100.0 * np.sin(a), 3)])
    return out


def _write(folder, spec=SPEC, header=HEADER, rows=None):
    """Write a track JSON + CSV pair and return the JSON path."""
    folder.mkdir(parents=True, exist_ok=True)
    rows = _rows() if rows is None else rows
    lines = [",".join(header)] + [",".join(str(v) for v in r) for r in rows]
    (folder / "tracks.csv").write_text("\n".join(lines) + "\n")
    path = folder / "tracks.json"
    path.write_text(json.dumps(spec))
    return path


# ---------------------------------------------------------------------------
# The tracks themselves
# ---------------------------------------------------------------------------
def test_stroke_tracks_holds_valid_tracks():
    tr = _manual_tracks(np.linspace(120.0, 40.0, 10))
    assert tr.t.shape == (10,) and tr.butt.shape == tr.rod.shape == (10, 2)
    assert tr.m_per_unit == 1.0 and tr.y_axis == "up"
    assert tr.casting_direction == "right" and tr.butt_offset_m == 0.0
    assert tr.median_step == pytest.approx(0.01)
    with pytest.raises(ValueError, match="read-only"):
        tr.t[0] = 1.0
    px = _manual_tracks(np.linspace(120.0, 40.0, 10), units="px",
                        m_per_unit=0.004)
    assert px.y_axis == "down"


@pytest.mark.parametrize("change", [
    {"t": np.arange(7) / 100.0},                        # too few rows
    {"t": np.r_[np.arange(9), 8.0] / 100.0},            # repeated time
    {"t": np.r_[np.arange(9), np.inf] / 100.0},         # not finite
    {"butt": np.full((10, 2), np.nan)},                 # not finite
    {"rod": np.zeros((9, 2))},                          # wrong shape
    {"units": "mm"},
    {"units": "px"},                                    # pixels, no scale
    {"units": "px", "m_per_unit": 0.0},
    {"m_per_unit": 0.5},                                # metres with a scale
    {"y_axis": "sideways"},
    {"casting_direction": "forward"},
    {"butt_offset_m": -0.1},
    {"tracking_noise": 0.0},
    {"fps": -30.0},
    {"rsp_t": float("nan")},
    {"extra": {"tip": np.zeros((9, 2))}},               # wrong shape
    {"meta": {"units": "px"}},                          # a format key
])
def test_stroke_tracks_rejects_invalid(change):
    good = _manual_tracks(np.linspace(120.0, 40.0, 10))
    fields = {f.name: getattr(good, f.name) for f in dataclasses.fields(good)}
    fields |= {"m_per_unit": None, "y_axis": None} | change
    with pytest.raises(ValueError):
        StrokeTracks(**fields)


def test_load_tracks_reads_table_and_metadata(tmp_path):
    path = _write(tmp_path / "a")
    tr = load_tracks(path)
    rows = np.array(_rows(), dtype=float)
    assert tr.name == "file tracks"
    assert np.allclose(tr.t, rows[:, 0] / 100.0)
    assert np.array_equal(tr.butt, rows[:, 1:3])
    assert np.array_equal(tr.rod, rows[:, 3:5])
    assert tr.rsp_t == pytest.approx(0.06) and tr.fps == 100.0
    assert tr.units == "px" and tr.m_per_unit == 0.004
    assert tr.y_axis == "down" and tr.casting_direction == "right"
    assert tr.butt_offset_m == 0.05 and tr.tracking_noise == 1.5
    assert tr.meta == {"description": "from a file",
                       "source": {"camera": "phone"}}
    assert load_tracks(tmp_path / "a").name == "file tracks"   # the folder
    assert load_tracks(tr) is tr


def test_load_tracks_with_time_column(tmp_path):
    spec = {k: v for k, v in SPEC.items() if k != "fps"}
    spec["columns"] = {"t": "time", "butt_x": "bx", "butt_y": "by",
                       "rod_x": "rx", "rod_y": "ry"}
    spec["rsp"] = {"t": 1.25}
    rows = [[1.2 + 0.0125 * r[0], *r[1:]] for r in _rows()]
    tr = load_tracks(_write(tmp_path, spec, ["time", *HEADER[1:]], rows))
    assert np.allclose(tr.t, [r[0] for r in rows])
    assert tr.rsp_t == 1.25 and tr.fps is None


def test_scale_from_known_length(tmp_path):
    spec = SPEC | {"scale": {"length_m": 2.74, "from_px": [100, 700],
                             "to_px": [700, 1500]},
                   "butt_offset_m": 0.0}
    tr = load_tracks(_write(tmp_path, spec))
    assert tr.m_per_unit == pytest.approx(2.74 / 1000.0)
    ex = stroke_from_tracks(tr, smoothing=False)
    # the butt point moves 3 px per frame along +x
    assert np.allclose(np.diff(ex.hand_x), 3 * 2.74 / 1000.0)
    assert ex.stroke.meta["source"]["m_per_unit"] == pytest.approx(0.00274)


def test_rows_with_missing_points_are_skipped(tmp_path):
    rows = _rows(14)
    for i in (3, 9):
        rows[i][3] = ""                     # rod_x not tracked
    rows[5][1] = " "                        # butt_x not tracked
    tr = load_tracks(_write(tmp_path, rows=rows))
    assert tr.t.size == 11
    assert np.allclose(tr.t * 100.0, [0, 1, 2, 4, 6, 7, 8, 10, 11, 12, 13])
    ex = stroke_from_tracks(tr, smoothing=False)
    assert ex.stroke.t.size == 11


def _bad(spec=None, header=None, rows=None, **changes):
    spec = dict(SPEC if spec is None else spec) | changes
    return spec, HEADER if header is None else header, rows


def _without(*keys):
    return {k: v for k, v in SPEC.items() if k not in keys}


def _rows_with(i, j, value, n=10):
    rows = _rows(n)
    rows[i][j] = value
    return rows


BOTH = SPEC["columns"] | {"t": "frame"}
NEITHER = {k: v for k, v in SPEC["columns"].items() if k != "frame"}


@pytest.mark.parametrize("spec, header, rows", [
    _bad(kind="stroke"),
    _bad(_without("kind")),
    _bad(_without("name")),
    _bad(_without("columns")),
    _bad(_without("units")),
    _bad(_without("rsp")),
    _bad(_without("table_csv")),
    _bad(columns={k: v for k, v in SPEC["columns"].items() if k != "rod_y"}),
    _bad(columns=SPEC["columns"] | {"rod_y": "nope"}),     # not in the CSV
    _bad(columns=BOTH),
    _bad(columns=NEITHER),
    _bad(columns=SPEC["columns"] | {"tip_x": "bx"}),       # unpaired extra
    _bad(_without("fps")),
    _bad(fps=0),
    _bad(fps="fast"),
    _bad(units="mm"),
    _bad(_without("scale")),
    _bad(scale={"m_per_px": -0.004}),
    _bad(scale={"length_m": 2.74, "from_px": [1, 1]}),
    _bad(scale={"length_m": 2.74, "from_px": [1, 1], "to_px": [1, 1]}),
    _bad(units="m"),                                       # metres + a scale
    _bad(rsp={"frame": 3, "t": 0.03}),
    _bad(rsp={}),
    _bad(tracking_noise=-1.0),
    _bad(y_axis="sideways"),
    _bad(rows=_rows_with(4, 2, "nan")),
    _bad(rows=_rows_with(4, 2, "inf")),
    _bad(rows=_rows_with(4, 2, "abc")),
    _bad(rows=_rows_with(4, 0, 3)),                        # repeated time
    _bad(rows=_rows_with(4, 0, "")),                       # no time
    _bad(rows=_rows(7)),
    _bad(rows=_rows_with(2, 1, "", n=8)),                  # 7 rows remain
])
def test_load_tracks_rejects_invalid(tmp_path, spec, header, rows):
    path = _write(tmp_path, spec, header, rows)
    with pytest.raises(ValueError):
        load_tracks(path)


def test_load_tracks_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_tracks(tmp_path / "nowhere")
    path = _write(tmp_path)
    (tmp_path / "tracks.csv").unlink()
    with pytest.raises(FileNotFoundError):
        load_tracks(path)


def test_save_tracks_round_trip(tmp_path, cast1):
    tr = tracks_from_stroke(cast1, fps=FPS, noise=1.0, seed=3,
                            butt_offset_m=0.07, casting_direction="left")
    tip = tr.rod + 5.0
    tip = np.where(np.arange(tip.shape[0])[:, None] % 9 == 0, np.nan, tip)
    tr = dataclasses.replace(tr, extra={"tip": tip},
                             meta=tr.meta | {"description": "round trip"})
    back = load_tracks(save_tracks(tr, tmp_path / "out"))
    assert back.name == tr.name and back.meta == tr.meta
    for key in ("t", "butt", "rod"):
        assert np.array_equal(getattr(back, key), getattr(tr, key))
    assert np.array_equal(back.extra["tip"], tip, equal_nan=True)
    for key in ("rsp_t", "units", "m_per_unit", "y_axis", "casting_direction",
                "butt_offset_m", "tracking_noise", "fps"):
        assert getattr(back, key) == getattr(tr, key), key
    metres = tracks_from_stroke(cast1, units="m")
    back = load_tracks(save_tracks(metres, tmp_path / "m"))
    assert back.units == "m" and back.m_per_unit == 1.0
    assert back.tracking_noise is None and np.array_equal(back.rod, metres.rod)


def test_synthetic_tracks_are_reproducible(cast1):
    a = tracks_from_stroke(cast1, fps=FPS, m_per_px=SCALE, noise=1.0, seed=7)
    b = tracks_from_stroke(cast1, fps=FPS, m_per_px=SCALE, noise=1.0, seed=7)
    c = tracks_from_stroke(cast1, fps=FPS, m_per_px=SCALE, noise=1.0, seed=8)
    assert np.array_equal(a.butt, b.butt) and np.array_equal(a.rod, b.rod)
    assert not np.array_equal(a.rod, c.rod)
    assert a.tracking_noise == 1.0 and a.fps == FPS
    clean = tracks_from_stroke(cast1, fps=FPS, m_per_px=SCALE,
                               rod_point_m=ROD_POINT)
    dist = np.hypot(*(clean.rod - clean.butt).T)
    assert np.allclose(dist, ROD_POINT / SCALE)
    assert np.allclose(np.diff(clean.t), 1.0 / FPS)
    assert clean.tracking_noise is None
    paused = tracks_from_stroke(cast1, fps=FPS, pause_s=0.1)
    assert paused.rsp_t == pytest.approx(clean.rsp_t + 0.1)
    assert paused.t[-1] == pytest.approx(clean.t[-1] + 0.2, abs=1.0 / FPS)
    assert np.allclose(paused.butt[:20], paused.butt[0])   # held still


# ---------------------------------------------------------------------------
# Conversion without smoothing
# ---------------------------------------------------------------------------
def test_synthetic_tracks_round_trip(cast1):
    tr = tracks_from_stroke(cast1, fps=FPS, m_per_px=SCALE,
                            butt_offset_m=0.08)
    ex = stroke_from_tracks(tr, smoothing=False)
    assert isinstance(ex, StrokeExtraction) and isinstance(ex.stroke, Stroke)
    angle, hx, hy = _truth(cast1, ex.stroke.t)
    assert np.abs(ex.stroke.angle_deg - angle).max() < 1e-3
    assert np.abs(ex.stroke.hand_x - hx).max() < 1e-5
    assert np.abs(ex.stroke.hand_y - hy).max() < 1e-5


def test_stroke_time_is_relative_to_rsp(tmp_path):
    tr = load_tracks(_write(tmp_path))
    ex = stroke_from_tracks(tr, smoothing=False)
    assert np.allclose(ex.stroke.t, (np.arange(10) - 6) / 100.0)
    assert ex.stroke.t_span == pytest.approx((-0.06, 0.03))
    assert np.allclose(ex.t, ex.stroke.t)


@pytest.mark.parametrize("frame", [-1, 10])
def test_rsp_outside_track_is_rejected(tmp_path, frame):
    tr = load_tracks(_write(tmp_path, SPEC | {"rsp": {"frame": frame}}))
    with pytest.raises(ValueError, match="RSP"):
        stroke_from_tracks(tr)


def test_angle_from_points():
    known = np.linspace(200.0, 30.0, 18)          # sweeps through 180 deg
    ex = stroke_from_tracks(_manual_tracks(known), smoothing=False)
    assert np.allclose(ex.stroke.angle_deg, known)
    assert np.allclose(ex.angle_deg, known)
    assert np.abs(np.diff(ex.stroke.angle_deg)).max() < 15.0
    # image coordinates: y down, and a cast towards the left of the frame
    butt = np.tile([300.0, 500.0], (8, 1))
    up = StrokeTracks(name="up", t=np.arange(8) / 100.0, butt=butt,
                      rod=butt + [0.0, -100.0], rsp_t=0.03, m_per_unit=0.004)
    assert np.allclose(stroke_from_tracks(up, smoothing=False)
                       .stroke.angle_deg, 90.0)
    left = dataclasses.replace(up, rod=butt + [-100.0, 0.0],
                               casting_direction="left")
    assert np.allclose(stroke_from_tracks(left, smoothing=False)
                       .stroke.angle_deg, 0.0)


def test_coincident_points_are_rejected():
    tr = _manual_tracks(np.linspace(120.0, 40.0, 10))
    rod = tr.rod.copy()
    rod[4] = tr.butt[4]
    with pytest.raises(ValueError, match="coincide"):
        stroke_from_tracks(dataclasses.replace(tr, rod=rod))


def test_butt_offset_is_corrected(cast1):
    at_end = stroke_from_tracks(tracks_from_stroke(cast1), smoothing=False)
    up_rod = tracks_from_stroke(cast1, butt_offset_m=0.10)
    moved = stroke_from_tracks(up_rod, smoothing=False)
    assert np.allclose(moved.stroke.hand_x, at_end.stroke.hand_x, atol=1e-9)
    assert np.allclose(moved.stroke.hand_y, at_end.stroke.hand_y, atol=1e-9)
    # without the correction the hand path is wrong by centimetres
    wrong = stroke_from_tracks(dataclasses.replace(up_rod, butt_offset_m=0.0),
                               smoothing=False)
    assert np.abs(wrong.stroke.hand_x - at_end.stroke.hand_x).max() > 0.05


@pytest.mark.parametrize("kwargs", [{"smoothing": False}, {},
                                    {"noise": 2.0}])
def test_hand_origin_at_rsp(cast1, kwargs):
    tr = tracks_from_stroke(cast1, fps=113.0, noise=1.0, seed=1,
                            origin=(800.0, 600.0))
    tr = dataclasses.replace(tr, tracking_noise=None)
    stroke = stroke_from_tracks(tr, **kwargs).stroke
    x, y = stroke.hand_xy(0.0)
    assert abs(float(x)) < 1e-12 and abs(float(y)) < 1e-12


def test_orientation_and_units_give_same_stroke(cast1):
    metres = tracks_from_stroke(cast1, units="m")
    pixels = tracks_from_stroke(cast1, units="px", m_per_px=SCALE,
                                y_axis="down", casting_direction="left",
                                origin=(1200.0, 700.0))
    assert metres.y_axis == "up" and pixels.y_axis == "down"
    a = stroke_from_tracks(metres, smoothing=False).stroke
    b = stroke_from_tracks(pixels, smoothing=False).stroke
    assert np.allclose(a.t, b.t)
    assert np.allclose(a.angle_deg, b.angle_deg, atol=1e-9)
    assert np.allclose(a.hand_x, b.hand_x, atol=1e-9)
    assert np.allclose(a.hand_y, b.hand_y, atol=1e-9)


def test_extra_points_kept_and_ignored(tmp_path, cast1):
    spec = SPEC | {"columns": SPEC["columns"] | {"tip_x": "tx",
                                                 "tip_y": "ty"}}
    rows = [[*r, 900.0 + r[0], 100.0] for r in _rows()]
    rows[2][5] = ""                                   # tip hidden in a frame
    with_tip = load_tracks(_write(tmp_path / "tip", spec,
                                  [*HEADER, "tx", "ty"], rows))
    plain = load_tracks(_write(tmp_path / "plain"))
    assert with_tip.t.size == 10 and plain.extra == {}
    assert with_tip.extra["tip"][5] == pytest.approx([905.0, 100.0])
    assert np.isnan(with_tip.extra["tip"][2, 0])
    for kwargs in ({"smoothing": False}, {}):
        a = stroke_from_tracks(with_tip, **kwargs).stroke
        b = stroke_from_tracks(plain, **kwargs).stroke
        assert np.array_equal(a.t, b.t)
        assert np.array_equal(a.angle_deg, b.angle_deg)
        assert np.array_equal(a.hand_x, b.hand_x)


def test_smoothing_off_keeps_raw_samples(cast1):
    tr = tracks_from_stroke(cast1, fps=FPS, noise=1.0, seed=2, pause_s=0.1)
    ex = stroke_from_tracks(tr, smoothing=False)
    assert np.array_equal(ex.stroke.t, ex.t)
    assert np.allclose(ex.t, tr.t - tr.rsp_t)
    assert np.array_equal(ex.stroke.angle_deg, ex.angle_deg)
    assert np.array_equal(ex.stroke.hand_x, ex.hand_x)
    assert np.array_equal(ex.stroke.hand_y, ex.hand_y)
    assert ex.rms_angle_deg == 0.0 and ex.rms_hand_m == 0.0
    assert ex.stroke.meta["source"]["smoothing"] == "none"


# ---------------------------------------------------------------------------
# Smoothing, resampling and reporting
# ---------------------------------------------------------------------------
def _peak_angular_acceleration(stroke):
    dt = np.diff(stroke.t)[0]
    return np.abs(np.diff(stroke.angle_deg, 2)).max() / dt ** 2


@pytest.mark.parametrize("noise", [0.5, 1.0, 2.0])
def test_residual_matches_stated_noise(cast1, noise):
    tr = tracks_from_stroke(cast1, fps=FPS, m_per_px=SCALE, noise=noise,
                            seed=11, pause_s=0.1)
    ex = stroke_from_tracks(tr)                 # the noise is in the tracks
    assert 0.7 < ex.rms_hand_m / (noise * SCALE) < 1.3
    again = stroke_from_tracks(dataclasses.replace(tr, tracking_noise=None),
                               noise=noise)     # ... or an argument
    assert again.rms_hand_m == pytest.approx(ex.rms_hand_m)
    for bad in (0.0, -1.0, float("nan")):
        with pytest.raises(ValueError, match="noise"):
            stroke_from_tracks(tr, noise=bad)


def test_more_noise_gives_smoother_stroke(cast1):
    tr = tracks_from_stroke(cast1, fps=FPS, noise=1.0, seed=5, pause_s=0.1)
    small = stroke_from_tracks(tr, noise=0.3)
    large = stroke_from_tracks(tr, noise=3.0)
    assert (_peak_angular_acceleration(large.stroke)
            < _peak_angular_acceleration(small.stroke))
    assert large.rms_angle_deg > small.rms_angle_deg


@pytest.mark.parametrize("seed", range(4))
def test_automatic_smoothing_reduces_error(cast1, seed):
    tr = tracks_from_stroke(cast1, fps=FPS, noise=1.0, seed=seed,
                            pause_s=0.1)
    ex = stroke_from_tracks(dataclasses.replace(tr, tracking_noise=None))
    assert "cross-validation" in ex.stroke.meta["source"]["smoothing"]
    assert ex.stroke.meta["source"]["tracking_noise"] == "automatic"
    true_raw, _, _ = _truth(cast1, ex.t)
    raw_error = np.sqrt(np.mean((ex.angle_deg - true_raw) ** 2))
    smooth_error = np.sqrt(np.mean(
        (np.rad2deg(ex.stroke.angle(ex.t)) - true_raw) ** 2))
    assert smooth_error < 0.6 * raw_error


def test_smoothed_stroke_is_dense(tmp_path, cast1):
    tr = tracks_from_stroke(cast1, fps=60.0, noise=1.0, seed=0, pause_s=0.1)
    with pytest.warns(UserWarning, match="frame rate"):
        stroke = stroke_from_tracks(tr).stroke
    assert np.allclose(np.diff(stroke.t), 0.0025)
    assert np.any(stroke.t == 0.0)
    t0, t1 = tr.t[0] - tr.rsp_t, tr.t[-1] - tr.rsp_t
    assert t0 <= stroke.t[0] < t0 + 0.0025 and t1 - 0.0025 < stroke.t[-1] <= t1
    path = save_stroke(stroke, tmp_path)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert np.array_equal(load_stroke(path).t, stroke.t)
    with pytest.warns(UserWarning):
        coarse = stroke_from_tracks(tr, dt=0.005).stroke
    assert np.allclose(np.diff(coarse.t), 0.005) and np.any(coarse.t == 0.0)
    with pytest.raises(ValueError, match="dt"):
        stroke_from_tracks(tr, dt=0.0)


def test_result_reports_raw_samples_and_fit(cast1):
    tr = tracks_from_stroke(cast1, fps=FPS, noise=1.0, seed=4, pause_s=0.1)
    ex = stroke_from_tracks(tr)
    n = tr.t.size
    assert ex.t.shape == ex.angle_deg.shape == (n,)
    assert ex.hand_x.shape == ex.hand_y.shape == (n,)
    angle = np.rad2deg(ex.stroke.angle(ex.t))
    hx, hy = ex.stroke.hand_xy(ex.t)
    assert ex.rms_angle_deg == pytest.approx(
        np.sqrt(np.mean((angle - ex.angle_deg) ** 2)))
    assert ex.rms_hand_m == pytest.approx(np.sqrt(np.mean(
        ((hx - ex.hand_x) ** 2 + (hy - ex.hand_y) ** 2) / 2.0)))
    assert ex.rms_angle_deg > 0.0 and ex.rms_hand_m > 0.0


def test_extracted_stroke_metadata(tmp_path, cast1):
    tr = tracks_from_stroke(cast1, fps=FPS, m_per_px=SCALE, noise=1.0,
                            seed=6, pause_s=0.1, butt_offset_m=0.05)
    ex = stroke_from_tracks(tr, name="my stroke")
    stroke = load_stroke(save_stroke(ex.stroke, tmp_path))
    assert stroke.name == "my stroke"
    source = stroke.meta["source"]
    assert source["method"] == "tracks" and source["tracks"] == tr.name
    assert source["samples"] == tr.t.size
    assert source["median_step_s"] == pytest.approx(1.0 / FPS)
    assert "Reinsch" in source["smoothing"]
    assert source["tracking_noise"] == 1.0
    assert source["tracking_noise_units"] == "px"
    assert source["rms_angle_deg"] == pytest.approx(ex.rms_angle_deg)
    assert source["rms_hand_m"] == pytest.approx(ex.rms_hand_m)
    assert source["m_per_unit"] == SCALE and source["butt_offset_m"] == 0.05
    assert source["capture_fps"] == FPS
    assert source["tracks_source"]["method"] == "synthetic"


def test_coarse_track_warns(cast1):
    tr = tracks_from_stroke(cast1, fps=30.0, pause_s=0.1)
    with pytest.warns(UserWarning, match="frame rate") as record:
        ex = stroke_from_tracks(tr)
    assert "30 frames per second" in str(record[0].message)
    assert ex.stroke.t.size > 100


def test_fine_track_at_rest_does_not_warn(cast1):
    tr = tracks_from_stroke(cast1, fps=FPS, pause_s=0.1)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        stroke_from_tracks(tr)
        stroke_from_tracks(tr, smoothing=False)


def test_track_ending_in_motion_warns(cast1):
    tr = tracks_from_stroke(cast1, fps=FPS, pause_s=0.1)
    keep = tr.t <= tr.rsp_t                    # cut the clip at RSP
    cut = dataclasses.replace(tr, t=tr.t[keep], butt=tr.butt[keep],
                              rod=tr.rod[keep])
    with pytest.warns(UserWarning, match="ends while the angle") as record:
        ex = stroke_from_tracks(cut)
    assert len(record) == 1
    assert "track starts" not in str(record[0].message)
    assert ex.stroke.t[-1] == pytest.approx(0.0, abs=0.0025)


@pytest.mark.parametrize("seed", range(6))
def test_noisy_track_with_pauses_does_not_warn(cast1, seed):
    tr = tracks_from_stroke(cast1, fps=FPS, noise=1.0, seed=seed,
                            pause_s=0.1)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        stroke_from_tracks(tr)
        stroke_from_tracks(dataclasses.replace(tr, tracking_noise=None))


# ---------------------------------------------------------------------------
# Recovering a known stroke
# ---------------------------------------------------------------------------
def test_recovers_cast1_without_noise(cast1):
    tr = tracks_from_stroke(cast1, fps=FPS, m_per_px=SCALE,
                            rod_point_m=ROD_POINT)
    stroke = stroke_from_tracks(tr).stroke
    angle, hx, hy = _truth(cast1, stroke.t)
    assert np.abs(stroke.angle_deg - angle).max() < 0.2
    assert np.hypot(stroke.hand_x - hx, stroke.hand_y - hy).max() < 1e-3


@pytest.mark.parametrize("seed", range(5))
def test_recovers_cast1_with_noise(cast1, seed):
    tr = tracks_from_stroke(cast1, fps=FPS, m_per_px=SCALE,
                            rod_point_m=ROD_POINT, noise=1.0, seed=seed)
    stroke = stroke_from_tracks(tr).stroke      # the noise is stated
    angle, hx, hy = _truth(cast1, stroke.t)
    rms_angle = np.sqrt(np.mean((stroke.angle_deg - angle) ** 2))
    rms_hand = np.sqrt(np.mean((stroke.hand_x - hx) ** 2
                               + (stroke.hand_y - hy) ** 2))
    assert rms_angle < 0.5
    assert rms_hand < 3e-3
