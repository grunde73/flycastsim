# -*- coding: utf-8 -*-
"""Tests for the ``rod.yaml`` loader (:mod:`flycastsim.rod.measurement`).

Uses a minimal ``rod.yaml`` written to a temporary folder, plus the real
measurement configs in ``assets/`` when they are present.
"""
from pathlib import Path

import numpy as np
import pytest

from flycastsim.rod import load_rod_measurement

ASSETS = Path(__file__).resolve().parents[2] / "assets"

MINIMAL = """\
schema: flycastsim.rod.measurement/1
id: TEST
make: Acme
model: Test 905-2
rod:
  length_m: 2.70
  sections:
  - {name: butt, mass_g: 60.0, length_m: 1.40, mass_center_m: 0.30}
  - {name: tip, mass_g: 12.0, length_m: 1.40, mass_center_m: 0.60}
  ferrule_overlap_m: null
mount:
  clamp_s_m: 0.25
  clamp_angle_deg: 2.0
calibration:
  clamp_px: [900, 50]
static_bend:
  images_dir: frames
  first_frame: image_0001.jpg
  last_frame: image_0003.jpg
  trace_start_px: [880, 50]
  trace_direction: [-1, 0]
  load_step_g: null
ccs:
  ip_g: 90.0
  deflection_fraction: 0.3333
frequency_test:
  csv: freq.csv
"""


@pytest.fixture
def rod_dir(tmp_path):
    (tmp_path / "rod.yaml").write_text(MINIMAL)
    (tmp_path / "freq.csv").write_text("m[g],f[hz]\n0,2.5\n10,1.2\n")
    frames = tmp_path / "frames"
    frames.mkdir()
    for i in range(5):
        (frames / f"image_{i:04d}.jpg").write_bytes(b"")
    return tmp_path


def test_load_minimal(rod_dir):
    m = load_rod_measurement(rod_dir)
    assert m.id == "TEST" and m.label == "Acme Test 905-2"
    assert m.free_length == pytest.approx(2.45)
    assert m.clamp_angle == pytest.approx(np.radians(2.0))
    assert [s.mass for s in m.sections] == pytest.approx([0.060, 0.012])
    assert [p.name for p in m.frame_paths()] == [
        "image_0001.jpg", "image_0002.jpg", "image_0003.jpg"]
    ccs = m.ccs_data()
    assert ccs.ip_mass == pytest.approx(0.090)
    f = m.frequency_data()
    assert f.tip_masses == pytest.approx([0.0, 0.010])
    assert f.frequencies == pytest.approx([2.5, 1.2])


def test_mass_model_from_sections(rod_dir):
    model = load_rod_measurement(rod_dir).mass_model(has_reel_seat=False)
    # overlap from the assembled length: 2.80 - 2.70 over one joint
    assert model.ferrule_overlap == pytest.approx(0.10)
    assert model.initial_params() == pytest.approx([0.060, 0.30, 0.012, 0.60])


def test_mass_model_guess_without_sections(rod_dir):
    text = (rod_dir / "rod.yaml").read_text().replace(
        "mass_g: 60.0", "mass_g: null")
    (rod_dir / "rod.yaml").write_text(text)
    m = load_rod_measurement(rod_dir)
    assert m.sections is None
    model = m.mass_model(n_sections=3)
    assert len(model.lengths) == 3
    assert sum(model.masses) == pytest.approx(0.090)
    assert model.mass_sigma is None          # masses left free


def test_image_transform_from_config(rod_dir):
    tr = load_rod_measurement(rod_dir).image_transform(scale=1e-3)
    assert tr.clamp_px == pytest.approx([900, 50])
    assert tr.rod_points_left


def test_rejects_unknown_schema(rod_dir):
    text = (rod_dir / "rod.yaml").read_text().replace("/1", "/99")
    (rod_dir / "rod.yaml").write_text(text)
    with pytest.raises(ValueError, match="schema"):
        load_rod_measurement(rod_dir)


@pytest.mark.skipif(not (ASSETS / "PA905" / "rod.yaml").exists(),
                    reason="rod assets missing")
@pytest.mark.parametrize("rod, n_frames, has_sections",
                         [("PA905", 38, False), ("XP590", 24, True),
                          ("TCR590", 16, True)])
def test_bundled_rod_configs(rod, n_frames, has_sections):
    m = load_rod_measurement(ASSETS / rod)
    assert m.id == rod
    assert m.clamp_s == pytest.approx(0.25)
    assert (m.sections is not None) == has_sections
    assert len(m.frame_paths()) == n_frames
    assert m.ccs_data() is not None and m.frequency_data() is not None
