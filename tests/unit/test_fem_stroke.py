"""Casting strokes as data (``cast-stroke`` spec)."""
import json
import warnings

import numpy as np
import pytest

from flycastsim.fem import Stroke, bundled_stroke_path, load_stroke, save_stroke


def _stroke(step=0.005, hand=True):
    """A smooth test stroke on ``[-0.4, 0.1]`` sampled every ``step`` s."""
    t = np.round(np.arange(-0.4, 0.1 + step / 2, step), 6)
    u = np.clip((t + 0.4) / 0.4, 0.0, 1.0)
    s = u * u * (3.0 - 2.0 * u)
    kwargs = {"hand_x": -0.3 + 0.4 * s, "hand_y": 0.1 * s} if hand else {}
    return Stroke(name="test", t=t, angle_deg=128.0 - 80.0 * s,
                  meta={"description": "a test", "source": {"by": "hand"}},
                  **kwargs)


def _write(folder, spec, header, rows):
    """Write a stroke JSON + CSV pair and return the JSON path."""
    folder.mkdir(parents=True, exist_ok=True)
    lines = [",".join(header)] + [",".join(str(v) for v in r) for r in rows]
    (folder / "stroke.csv").write_text("\n".join(lines) + "\n")
    path = folder / "stroke.json"
    path.write_text(json.dumps(spec))
    return path


FULL_SPEC = {"name": "file stroke", "kind": "stroke", "table_csv": "stroke.csv",
             "columns": {"t": "t_s", "angle": "angle_deg",
                         "x": "hand_x_m", "y": "hand_y_m"},
             "description": "from a file", "source": {"fps": 500}}
FULL_HEADER = ["t_s", "angle_deg", "hand_x_m", "hand_y_m"]
FULL_ROWS = [(-0.01, 120.0, -0.1, 0.0), (-0.005, 100.0, 0.0, 0.05),
             (0.0, 50.0, 0.1, 0.1)]


def test_stroke_passes_through_samples():
    """Evaluated at its sample times, a stroke returns the samples."""
    s = _stroke()
    assert np.allclose(np.rad2deg(s.angle(s.t)), s.angle_deg)
    x, y = s.hand_xy(s.t)
    assert np.allclose(x, s.hand_x)
    assert np.allclose(y, s.hand_y)


def test_stroke_holds_ends():
    """Outside the table the end values hold and the hand is at rest."""
    s = _stroke()
    before, after = s.t[0] - 0.2, s.t[-1] + 0.5
    assert np.isclose(np.rad2deg(s.angle(before)), s.angle_deg[0])
    assert np.isclose(np.rad2deg(s.angle(after)), s.angle_deg[-1])
    assert np.allclose(s.hand_xy(before), (s.hand_x[0], s.hand_y[0]))
    assert np.allclose(s.hand_xy(after), (s.hand_x[-1], s.hand_y[-1]))
    assert np.allclose(s.hand_vel(np.array([before, after])), 0.0)


def test_hand_velocity_is_position_derivative():
    """Inside the table the hand velocity is the derivative of the position."""
    s = _stroke()
    t = np.linspace(-0.38, 0.08, 47)
    h = 1e-6
    xp, yp = s.hand_xy(t + h)
    xm, ym = s.hand_xy(t - h)
    vx, vy = s.hand_vel(t)
    assert np.allclose(vx, (xp - xm) / (2 * h), atol=1e-5)
    assert np.allclose(vy, (yp - ym) / (2 * h), atol=1e-5)
    assert np.max(vx) > 0.5                      # the hand really moves


def test_stroke_without_hand_path_is_fixed(tmp_path):
    """A stroke file with only time and angle keeps the hand at the origin."""
    spec = {**FULL_SPEC, "columns": {"t": "t_s", "angle": "angle_deg"}}
    path = _write(tmp_path, spec, ["t_s", "angle_deg"],
                  [(r[0], r[1]) for r in FULL_ROWS])
    s = load_stroke(path)
    assert not s.has_hand_path
    t = np.linspace(-0.1, 0.1, 9)
    assert np.allclose(s.hand_xy(t), 0.0)
    assert np.allclose(s.hand_vel(t), 0.0)


def test_load_stroke_reads_table_and_metadata(tmp_path):
    """A full stroke file loads with its table values and metadata."""
    path = _write(tmp_path / "s", FULL_SPEC, FULL_HEADER, FULL_ROWS)
    rows = np.array(FULL_ROWS)
    for source in (path, path.parent):            # file or folder
        s = load_stroke(source)
        assert s.name == "file stroke"
        assert np.array_equal(s.t, rows[:, 0])
        assert np.array_equal(s.angle_deg, rows[:, 1])
        assert np.array_equal(s.hand_x, rows[:, 2])
        assert np.array_equal(s.hand_y, rows[:, 3])
        assert s.meta == {"description": "from a file", "source": {"fps": 500}}
    assert s.t_span == (-0.01, 0.0)


def _without(d, key):
    return {k: v for k, v in d.items() if k != key}


@pytest.mark.parametrize(("spec", "header", "rows", "match"), [
    ({**FULL_SPEC, "kind": "rod"}, FULL_HEADER, FULL_ROWS, "kind"),
    (_without(FULL_SPEC, "columns"), FULL_HEADER, FULL_ROWS, "columns"),
    (_without(FULL_SPEC, "name"), FULL_HEADER, FULL_ROWS, "name"),
    (FULL_SPEC, ["t_s", "angle_deg", "hand_x_m"],
     [r[:3] for r in FULL_ROWS], "hand_y_m"),
    ({**FULL_SPEC, "columns": {"t": "t_s", "angle": "angle_deg",
                               "x": "hand_x_m"}},
     FULL_HEADER, FULL_ROWS, "together"),
    (FULL_SPEC, FULL_HEADER, FULL_ROWS[:1], "two samples"),
    (FULL_SPEC, FULL_HEADER,
     [FULL_ROWS[0], (-0.005, "nan", 0.0, 0.0), FULL_ROWS[2]], "finite"),
    (FULL_SPEC, FULL_HEADER,
     [FULL_ROWS[0], FULL_ROWS[0], FULL_ROWS[2]], "increasing"),
    (FULL_SPEC, FULL_HEADER,
     [FULL_ROWS[1], FULL_ROWS[0], FULL_ROWS[2]], "increasing"),
], ids=["wrong-kind", "no-columns", "no-name", "missing-csv-column",
        "one-hand-column", "one-row", "not-finite", "repeated-time",
        "decreasing-time"])
def test_load_stroke_rejects_invalid(tmp_path, spec, header, rows, match):
    """A stroke file that breaks the format fails with a ValueError."""
    path = _write(tmp_path, spec, header, rows)
    with pytest.raises(ValueError, match=match):
        load_stroke(path)


def test_load_stroke_unknown_source(tmp_path):
    """A source that is neither a path nor a bundled name is not found."""
    with pytest.raises(FileNotFoundError):
        load_stroke("no-such-stroke")
    with pytest.raises(FileNotFoundError):
        load_stroke(tmp_path / "missing" / "stroke.json")


def test_coarse_stroke_warns(tmp_path):
    """A stroke sampled every 20 ms warns, and still loads."""
    path = save_stroke(_stroke(step=0.020), tmp_path)
    with pytest.warns(UserWarning, match="coarsely sampled"):
        s = load_stroke(path)
    assert len(s.t) == 26


def test_save_stroke_round_trip(tmp_path):
    """Saving and loading again gives back the same stroke."""
    for hand in (True, False):
        original = _stroke(hand=hand)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            loaded = load_stroke(save_stroke(original, tmp_path / str(hand)))
        assert loaded.name == original.name
        assert loaded.meta == original.meta
        assert np.array_equal(loaded.t, original.t)
        assert np.array_equal(loaded.angle_deg, original.angle_deg)
        if hand:
            assert np.array_equal(loaded.hand_x, original.hand_x)
            assert np.array_equal(loaded.hand_y, original.hand_y)
        else:
            assert loaded.hand_x is None


def test_bundled_stroke_path_points_into_package():
    """Bundled strokes resolve inside the installed package data."""
    path = bundled_stroke_path("cast1")
    assert path.parts[-4:] == ("data", "strokes", "cast1", "stroke.json")


def test_bundled_cast1_stroke_loads_clean():
    """The bundled Cast #1 stroke loads by name, densely and without a warning."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        s = load_stroke("cast1")
    assert s.name == "Cast #1 stroke"
    assert s.has_hand_path
    assert s.t_span == (-0.4, 0.13)
    assert len(s.t) == 213
    assert np.allclose(np.diff(s.t), 0.0025)
    assert "fitted by eye" in s.meta["source"]["method"].lower()
    assert s.meta["source"]["reference"].startswith("Grunde Løvoll")
