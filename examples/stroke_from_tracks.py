"""Make a casting stroke from points tracked in a video of a cast.

The points are tracked in another program and stored as track files
(``tracks.json`` + ``tracks.csv``, see ``docs/stroke_extraction.rst``).  This
script converts them to stroke files (``stroke.json`` + ``stroke.csv``) that
``simulate_cast1(stroke=...)`` can use.

    uv run python examples/stroke_from_tracks.py --tracks my_cast --out my_stroke
    uv run python examples/stroke_from_tracks.py --demo --out demo_stroke

``--demo`` needs no video: it first writes synthetic tracks, made from the
bundled Cast #1 stroke with one pixel of tracking noise, and converts those.
"""

from __future__ import annotations

import argparse
import tempfile
import warnings
from pathlib import Path

from flycastsim.fem import (
    load_tracks,
    save_stroke,
    save_tracks,
    stroke_from_tracks,
    tracks_from_stroke,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--tracks", type=Path,
                        help="folder with tracks.json, or the file itself")
    source.add_argument("--demo", action="store_true",
                        help="use synthetic tracks of the Cast #1 stroke")
    parser.add_argument("--out", type=Path, required=True,
                        help="folder to write stroke.json and stroke.csv to")
    parser.add_argument("--noise", type=float, default=None,
                        help="tracking noise per coordinate, in the units of "
                             "the table (default: 'tracking_noise' of the "
                             "tracks, else chosen from the data)")
    parser.add_argument("--dt", type=float, default=0.0025,
                        help="time step of the stroke table [s]")
    parser.add_argument("--no-smoothing", action="store_true",
                        help="keep the raw samples as the stroke table")
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory() as tmp:
        if args.demo:
            demo = tracks_from_stroke("cast1", fps=240, m_per_px=0.003,
                                      butt_offset_m=0.10, pause_s=0.1,
                                      noise=1.0, seed=0)
            args.tracks = save_tracks(demo, Path(tmp) / "demo_tracks")
            print(f"Wrote synthetic tracks to {args.tracks}")
        tracks = load_tracks(args.tracks)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = stroke_from_tracks(tracks, noise=args.noise, dt=args.dt,
                                        smoothing=not args.no_smoothing)
    stroke = result.stroke
    path = save_stroke(stroke, args.out)

    source = stroke.meta["source"]
    print(f"Tracks:      {tracks.name}")
    print(f"Samples:     {source['samples']} "
          f"(median step {source['median_step_s'] * 1e3:.2f} ms)")
    print(f"Smoothing:   {source['smoothing']} "
          f"(tracking noise: {source['tracking_noise']})")
    print(f"Deviation:   {result.rms_angle_deg:.3f} deg in angle, "
          f"{result.rms_hand_m * 1e3:.2f} mm in hand position (RMS, stroke "
          f"against raw samples)")
    print(f"Stroke:      {stroke.t[0]:.3f} s to {stroke.t[-1]:.3f} s, "
          f"{stroke.t.size} rows")
    for w in caught:
        print(f"Warning:     {w.message}")
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
