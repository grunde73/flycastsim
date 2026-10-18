"""Fit the bending-stiffness and mass profiles of the T&T Paradigm 905-3.

End-to-end example of the rod profile fit (``docs/rod_profile.rst``):

1. load the measurement data set ``assets/PA905/rod.yaml``;
2. trace the rod centre line in the static-bend frames (tips from the
   hand-tracked tip marker) and get the pixel scale from the rod length;
3. fit EI(s), mu(s), the unknown load step and the image transform jointly
   to the bend frames, the tip-mass frequency test and the CCS point;
4. write the profiles in the FEM rod-CSV layout plus Plotly figures to
   ``assets/PA905/fit/``.

Run from the repository root::

    uv run python examples/rod_profile_pa905.py [--every 2] [--n-coef 8]

PA905 has no section-mass measurements, so mu(s) starts from a generic
guess for a three-piece rod (prior +-5 g per section) and is mainly informed
by the frequency test.  The plumb line on the wall shows the camera is level
to 0.05 deg, which gives a tight camera-roll prior.  The rod is strapped to
a heavy mount at the front and back of the handle; the handle flexes between
the straps, which is fitted as a rotational compliance of the clamp.  Frames
whose tip leaves the image are excluded in ``rod.yaml``.  A full fit takes
several minutes.
"""

from __future__ import annotations

import argparse
import math
import time
from pathlib import Path

import numpy as np

from flycastsim.rod import (MonotoneLogEI, ProfileFitProblem, fit_profile,
                            load_rod_measurement, plot_bend_fit,
                            plot_rod_profiles)

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rod", default=str(ROOT / "assets" / "PA905"))
    ap.add_argument("--every", type=int, default=2,
                    help="use every n-th bend frame")
    ap.add_argument("--n-points", type=int, default=30,
                    help="centre-line points per frame")
    ap.add_argument("--n-coef", type=int, default=8,
                    help="log-EI spline coefficients")
    ap.add_argument("--smoothness", type=float, default=0.01)
    ap.add_argument("--rigid-clamp", dest="compliance", action="store_false",
                    help="do not fit a rotational compliance of the mount")
    args = ap.parse_args()

    meas = load_rod_measurement(args.rod)
    print(f"{meas.id}: {meas.label}, free length {meas.free_length:.3f} m")

    t0 = time.time()
    frames, scale = meas.extract_bend_frames(every=args.every,
                                             n_points=args.n_points)
    print(f"traced {len(frames)} frames in {time.time() - t0:.0f} s, "
          f"scale {scale * 1e3:.4f} mm/px")

    # The clamp point is the front strap of the mount (well located); the
    # handle flexes between the straps, modelled as a rotational spring.
    transform = meas.image_transform(scale=scale, sigma_px=1.5,
                                     clamp_sigma_px=5.0,
                                     roll_sigma=math.radians(0.1),
                                     scale_sigma_rel=0.02)
    ei_model = MonotoneLogEI(meas.clamp_s, meas.length, n_coef=args.n_coef)
    problem = ProfileFitProblem(
        ei_model, meas.mass_model(mass_sigma=0.005), meas.length,
        meas.clamp_s, frames,
        load_step=0.005, frequency=meas.frequency_data(sigma=0.02),
        ccs=meas.ccs_data(sigma=0.01), smoothness=args.smoothness,
        transform=transform, robust=3.0,
        clamp_compliance=0.01, fit_clamp_compliance=args.compliance)

    t0 = time.time()
    res = fit_profile(problem, ei_params=ei_model.params_from_endpoints(
        40.0, 2.0), verbose=1)
    print(f"fit: {time.time() - t0:.0f} s, {res.optimize.nfev} evaluations, "
          f"cost {res.optimize.cost:.1f} for {res.optimize.fun.size} "
          f"residuals ({res.optimize.message})")

    fit = transform.fitted(res.transform_params)
    print(f"load step     {res.load_step * 1e3:.2f} g")
    print(f"clamp         ({fit.clamp_px[0]:.1f}, {fit.clamp_px[1]:.1f}) px")
    print(f"scale         {fit.scale * 1e3:.4f} mm/px")
    print(f"camera roll   {math.degrees(fit.roll):.3f} deg")
    print(f"clamp angle   {math.degrees(fit.clamp_angle_offset):+.2f} deg "
          "(offset)")
    print(f"mount compl.  {math.degrees(res.clamp_compliance):.3f} deg/(N m)")
    m = res.mass_params.reshape(-1, 2)
    for i, (mass, xc) in enumerate(m):
        print(f"section {i + 1}     {mass * 1e3:5.1f} g, balance point "
              f"{xc:.3f} m")
    s = np.linspace(meas.clamp_s, meas.length, 9)
    print("s [m]        " + " ".join(f"{v:6.2f}" for v in s))
    print("EI [N m^2]   " + " ".join(f"{v:6.2f}" for v in res.EI(s)))
    print("mu [g/m]     " + " ".join(f"{v:6.1f}" for v in 1e3 * res.mu(s)))

    f_model = None
    if problem.frequency is not None:
        from flycastsim.rod import frequency_vs_tip_mass
        f_model = frequency_vs_tip_mass(
            res.EI, res.mu, problem.frequency.tip_masses, length=meas.length,
            s_clamp=meas.clamp_s, breakpoints=problem.mass_model.breakpoints)
        print("freq meas    " + " ".join(
            f"{v:5.2f}" for v in problem.frequency.frequencies))
        print("freq model   " + " ".join(f"{v:5.2f}" for v in f_model))

    out = Path(args.rod) / "fit"
    out.mkdir(exist_ok=True)
    table = res.table(41)
    np.savetxt(out / "rod_profile.csv",
               np.column_stack([table["s_m"], table["m_kg_per_m"],
                                table["EI_Nm2"]]),
               delimiter=",", fmt="%.6g", comments="",
               header="s_m,m_kg_per_m,EI_Nm2")
    plot_rod_profiles(res).write_html(out / "profiles.html")
    plot_bend_fit(res, every=2).write_html(out / "bend_fit.html")
    print(f"wrote {out}/rod_profile.csv, profiles.html, bend_fit.html")


if __name__ == "__main__":
    main()
