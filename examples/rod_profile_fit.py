"""Fit the bending-stiffness and mass profiles of a measured rod.

End-to-end example of the rod profile fit (``docs/rod_profile.rst``):

1. load a measurement data set ``assets/<ROD>/rod.yaml`` (default PA905);
2. trace the rod centre line in the static-bend frames (tips from the
   hand-tracked tip marker where available, otherwise traced tips checked
   against the constant rod length) and get the pixel scale from the rod
   length;
3. fit EI(s), mu(s), the unknown tip load of each frame (the load steps of
   the bead sequences are not constant), the mount compliance and the image
   transform jointly to the bend frames, the tip-mass frequency test and
   the CCS point;
4. write the fitted rod as an FEM component (``rod.json`` + ``rod.csv``,
   loadable with ``flycastsim.fem.components.load_component``), a
   ``fit_summary.json`` and Plotly figures to ``assets/<ROD>/fit/``.

Run from the repository root::

    uv run python examples/rod_profile_fit.py [--rod assets/XP590] [--preset quick]

``--install`` also copies ``rod.json``, ``rod.csv`` and ``fit_summary.json``
into the package's bundled fitted rods (``data/components/fitted_rods/``).

Measured section masses and balance points (XP590, TCR590) are used with
their default priors (+-0.2 g, +-5 mm).  PA905 has none, so its mu(s)
starts from a generic guess for a three-piece rod (prior +-5 g per section)
and is mainly informed by the frequency test.  The plumb line on the wall
shows the camera is level to 0.05 deg, which gives a tight camera-roll
prior.  The rod is strapped to
a heavy mount at the front and back of the handle; the handle flexes between
the straps, which is fitted as a rotational compliance of the clamp.  Frames
whose tip leaves the image are excluded in ``rod.yaml``.  A full fit takes
several minutes.
"""

from __future__ import annotations

import argparse
import math
import shutil
import time
from pathlib import Path

import numpy as np

from flycastsim.rod import load_rod_measurement, plot_bend_fit, plot_rod_profiles
from flycastsim.rod.fitted import fitted_rods_folder
from flycastsim.rod.measurement import FIT_PRESETS, export_fit, fit_rod

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rod", default=str(ROOT / "assets" / "PA905"))
    ap.add_argument("--preset", choices=sorted(FIT_PRESETS), default="full")
    ap.add_argument("--install", action="store_true",
                    help="copy the fitted rod into the package data")
    args = ap.parse_args()

    meas = load_rod_measurement(args.rod)
    print(f"{meas.id}: {meas.label}, free length {meas.free_length:.3f} m")

    t0 = time.time()
    res = fit_rod(meas, args.preset)
    print(f"fit ({args.preset}): {time.time() - t0:.0f} s, "
          f"{res.optimize.nfev} evaluations, cost {res.optimize.cost:.1f} "
          f"for {res.optimize.fun.size} residuals ({res.optimize.message})")

    out = Path(args.rod) / "fit"
    notes = [f"{meas.id} ({meas.label}): fitted EI(s) and mu(s), "
             f"{time.strftime('%Y-%m-%d')}",
             f"examples/rod_profile_fit.py --preset {args.preset}"]
    rod = export_fit(meas, res, out, notes=notes, preset=args.preset)
    summary = rod.summary
    tr = summary["image_transform"]
    print("loads [g]     " + " ".join(
        f"{1e3 * m:5.1f}" for m in summary["frame_added_mass_kg"]))
    print(f"mount compl.  "
          f"{math.degrees(summary['clamp_compliance_rad_per_Nm']):.3f} "
          f"deg/(N m), camera roll "
          f"{math.degrees(tr['camera_roll_rad']):.3f} deg, clamp angle "
          f"{math.degrees(tr['clamp_angle_offset_rad']):+.2f} deg")
    s = np.linspace(meas.clamp_s, meas.length, 9)
    print("s [m]         " + " ".join(f"{v:6.2f}" for v in s))
    print("EI [N m^2]    " + " ".join(f"{v:6.2f}" for v in rod.EI(s)))
    print("mu [g/m]      " + " ".join(f"{v:6.1f}" for v in 1e3 * rod.mu(s)))
    if "frequency" in summary:
        f = summary["frequency"]
        print("freq meas     " + " ".join(f"{v:5.2f}"
                                          for v in f["measured_hz"]))
        print("freq model    " + " ".join(f"{v:5.2f}" for v in f["model_hz"]))
    print(f"swingweight   {rod.swingweight_gm2:.1f} g m^2, "
          f"mass {rod.mass_g:.1f} g")

    # plotly.js from a CDN keeps the pages small enough to commit
    plot_rod_profiles(res).write_html(out / "profiles.html",
                                      include_plotlyjs="cdn")
    plot_bend_fit(res, every=2).write_html(out / "bend_fit.html",
                                           include_plotlyjs="cdn")
    print(f"wrote {out}/")
    if args.install:
        dest = fitted_rods_folder() / meas.id
        dest.mkdir(parents=True, exist_ok=True)
        for name in ("rod.json", "rod.csv", "fit_summary.json"):
            shutil.copy2(out / name, dest / name)
        print(f"installed into {dest}/")


if __name__ == "__main__":
    main()
