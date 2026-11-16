"""How much tracking noise and how low a frame rate does a cast tolerate?

Synthetic tracks are made from the bundled Cast #1 stroke for a grid of frame
rates and tracking-noise levels, a stroke is extracted from each, and
``simulate_cast1`` is run with it.  The table compares the extracted stroke
and the simulated rod with the run that uses the bundled stroke itself.

    uv run python examples/stroke_extraction_study.py
    uv run python examples/stroke_extraction_study.py --automatic --seeds 3
    uv run python examples/stroke_extraction_study.py --fps 240 --noise 1 \
        --m-per-px 0.0015 --rod-point 0.8

The tracks are optimistic: the rod is straight between the two tracked
points, the noise is independent from frame to frame, and the clip has a
0.1 s pause before and after the stroke.  See ``docs/stroke_extraction.rst``.
"""

from __future__ import annotations

import argparse
import dataclasses
import time
import warnings

import numpy as np

from flycastsim.fem import (
    load_stroke,
    simulate_cast1,
    stroke_from_tracks,
    tracks_from_stroke,
)

FPS = (500, 240, 120, 60, 30)
NOISE_PX = (0.0, 0.5, 1.0, 2.0)
M_PER_PX = 0.003
ROD_POINT_M = 0.40
PAUSE_S = 0.1


def _stroke_errors(stroke, truth):
    """RMS angle error [deg], RMS hand error [mm], peak angular speeds."""
    t = stroke.t
    hx, hy = truth.hand_xy(t)
    x0, y0 = truth.hand_xy(0.0)
    angle = np.rad2deg(truth.angle(t))
    rms_angle = np.sqrt(np.mean((stroke.angle_deg - angle) ** 2))
    rms_hand = np.sqrt(np.mean((stroke.hand_x - (hx - x0)) ** 2
                               + (stroke.hand_y - (hy - y0)) ** 2))
    peak = np.abs(np.gradient(stroke.angle_deg, t)).max()
    peak_true = np.abs(np.gradient(angle, t)).max()
    return rms_angle, rms_hand * 1e3, 100.0 * (peak / peak_true - 1.0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=5,
                        help="noise realisations per cell")
    parser.add_argument("--automatic", action="store_true",
                        help="choose the smoothing from the data instead of "
                             "stating the noise")
    parser.add_argument("--fps", type=float, nargs="+", default=FPS,
                        help="frame rates to test")
    parser.add_argument("--noise", type=float, nargs="+", default=NOISE_PX,
                        help="tracking-noise levels to test [px]")
    parser.add_argument("--m-per-px", type=float, default=M_PER_PX,
                        help="image scale [m/px]")
    parser.add_argument("--rod-point", type=float, default=ROD_POINT_M,
                        help="distance between the two tracked points [m]")
    args = parser.parse_args(argv)

    start = time.time()
    truth = load_stroke("cast1")
    _, _, _, _, chord0, defl0, _, _ = simulate_cast1()
    print(f"Reference run: chord shortens by "
          f"{(chord0.max() - chord0.min()) * 1e3:.0f} mm, tip deflection up "
          f"to {np.abs(defl0).max() * 1e3:.0f} mm")
    print(f"Smoothing: {'automatic' if args.automatic else 'noise stated'}; "
          f"{args.m_per_px * 1e3:g} mm/px, rod point {args.rod_point:g} m, "
          f"{args.seeds} seeds; mean (worst) over the seeds\n")
    print("| fps | noise [px] | angle RMS [deg] | hand RMS [mm] "
          "| peak ang. speed [%] | chord [mm] | tip deflection [mm] |")
    print("|---|---|---|---|---|---|---|")
    for fps in args.fps:
        for noise in args.noise:
            rows = []
            for seed in range(args.seeds if noise > 0.0 else 1):
                tracks = tracks_from_stroke(
                    truth, fps=fps, m_per_px=args.m_per_px,
                    rod_point_m=args.rod_point, pause_s=PAUSE_S, noise=noise,
                    seed=seed)
                if args.automatic:
                    tracks = dataclasses.replace(tracks, tracking_noise=None)
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    stroke = stroke_from_tracks(tracks).stroke
                _, _, _, _, chord, defl, _, _ = simulate_cast1(stroke=stroke)
                rows.append((*_stroke_errors(stroke, truth),
                             np.abs(chord - chord0).max() * 1e3,
                             np.abs(defl - defl0).max() * 1e3))
            rows = np.array(rows)
            mean, worst = rows.mean(axis=0), np.abs(rows).max(axis=0)
            cells = [f"{m:.2f} ({w:.2f})" if len(rows) > 1 else f"{m:.2f}"
                     for m, w in zip(mean, worst, strict=True)]
            print(f"| {fps:g} | {noise:g} | " + " | ".join(cells) + " |")
    print(f"\nRun time: {time.time() - start:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
