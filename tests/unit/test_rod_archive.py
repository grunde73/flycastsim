# -*- coding: utf-8 -*-
"""Tests for zipped rod data sets and fitted rods (rod.archive)."""
import io
import zipfile

import pytest

from flycastsim.rod.archive import extract_rod_archive, fitted_rod_zip


def _zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


@pytest.mark.parametrize("prefix", ["", "MYROD/"])
def test_extract_finds_rod_yaml(tmp_path, prefix):
    data = _zip({f"{prefix}rod.yaml": b"id: X\n",
                 f"{prefix}bend/image_0001.jpg": b"jpg",
                 "__MACOSX/._rod.yaml": b"junk"})
    folder = extract_rod_archive(data, tmp_path / "out")
    assert (folder / "rod.yaml").read_bytes() == b"id: X\n"
    assert (folder / "bend" / "image_0001.jpg").exists()
    assert not (tmp_path / "out" / "__MACOSX").exists()


@pytest.mark.parametrize("bad", ["../evil.txt", "/abs/evil.txt",
                                 "a/../../evil.txt"])
def test_extract_rejects_unsafe_paths(tmp_path, bad):
    data = _zip({"rod.yaml": b"id: X\n", bad: b"x"})
    with pytest.raises(ValueError, match="unsafe"):
        extract_rod_archive(data, tmp_path / "out")
    assert not (tmp_path / "evil.txt").exists()


def test_extract_rejects_missing_or_many_yaml(tmp_path):
    with pytest.raises(ValueError, match="exactly one"):
        extract_rod_archive(_zip({"x.txt": b"x"}), tmp_path / "a")
    with pytest.raises(ValueError, match="exactly one"):
        extract_rod_archive(_zip({"A/rod.yaml": b"", "B/rod.yaml": b""}),
                            tmp_path / "b")


def test_extract_rejects_oversized(tmp_path):
    data = _zip({"rod.yaml": b"x" * 1000})
    with pytest.raises(ValueError, match="too large"):
        extract_rod_archive(data, tmp_path / "out", max_bytes=100)


def test_fitted_rod_zip(tmp_path):
    for name in ("rod.json", "rod.csv", "fit_summary.json", "other.txt"):
        (tmp_path / name).write_text(name)
    with zipfile.ZipFile(io.BytesIO(fitted_rod_zip(tmp_path, "R1"))) as zf:
        assert sorted(zf.namelist()) == ["R1/fit_summary.json", "R1/rod.csv",
                                         "R1/rod.json"]


def test_measurement_zip_round_trip(tmp_path):
    """A zipped measurement extracts to a loadable data set with all
    frames, the frequency CSV and the background."""
    from pathlib import Path

    from flycastsim.rod import load_rod_measurement
    from flycastsim.rod.archive import measurement_zip

    src = Path(__file__).resolve().parents[2] / "assets" / "TCR590"
    if not (src / "rod.yaml").exists():
        pytest.skip("rod assets missing")
    meas = load_rod_measurement(src)
    folder = extract_rod_archive(measurement_zip(meas), tmp_path)
    copy = load_rod_measurement(folder)
    assert folder.name == "TCR590"
    assert len(copy.frame_paths()) == len(meas.frame_paths())
    assert copy.frequency_data() is not None
    assert (folder / "background.jpg").exists()
    assert not list(folder.rglob("*.mp4"))
