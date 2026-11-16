Casting strokes from video
==========================
**Status: implemented for tracked points** (open items at the end).  This page
describes how to turn a filmed cast into a casting stroke that drives the
simulation: how to film and track the cast, the track file format, the method,
how accurate the result is, and what is still open.

A *stroke* is the rod-butt angle and the hand position over time (see
"Casting strokes" in :doc:`fem`).  The library does
not read video.  You track two points on the rod in another program, write
them to *track files*, and :func:`flycastsim.fem.stroke_from_tracks` makes the
stroke:

.. code-block:: text

   video  -->  tracker program  -->  tracks.json + tracks.csv
                                             |
                                    stroke_from_tracks
                                             |
                                 stroke.json + stroke.csv  -->  simulate_cast1

Filming the cast
------------------------------
The stroke is two-dimensional, and the simulated cast is sensitive to small
errors in it (see `How accurate is it?`_), so the footage matters.

* **Fixed camera, square to the casting plane.**  Use a tripod and film from
  the side, with the camera axis at right angles to the direction of the cast.
  A view from an angle, a tilted casting plane or a wide-angle lens close to
  the caster distorts the stroke, and nothing corrects for it.
* **Slow motion.**  Film at 120 or 240 frames per second.  Below 100 frames
  per second the conversion warns: the stop takes about 50 ms, which is one or
  two frames at 30 frames per second.
* **Fill the frame with the caster.**  Only the hand and the lower rod are
  tracked, so the rod tip and the line need not be in view.  A closer view
  means fewer millimetres per pixel, which is what sets the accuracy.
* **Two marks on the rod.**  Put bright tape on the rod at the butt end, or
  just above the hand, and on the butt section 0.3 to 0.8 m further up.  The
  rod must be nearly straight between the marks.  Further apart gives a better
  angle; too far, and the bend of the rod under load biases it.
* **A known length in the frame**, in the casting plane: the distance between
  the two tape marks, or a measuring stick held where the caster stands.
* **Include the pause before the stroke and the follow-through after the
  stop.**  The simulation starts with the rod at rest and holds the last value
  of the stroke, so a clip that begins or ends while the rod is moving gives a
  jolt.  The conversion warns when it sees this.

Tracking the points
------------------------------
Track the two marks frame by frame in a video analysis program such as
`Tracker <https://opensourcephysics.github.io/tracker-website/>`_ or
`Kinovea <https://www.kinovea.org/>`_, and export a table with one row per
frame.  Then write a ``tracks.json`` next to the table that names its columns.

* ``butt`` is the mark at or near the rod butt.  Give its distance from the
  rod butt end as ``butt_offset_m``; the hand path is corrected to the butt
  end, which is where the model holds the rod.
* ``rod`` is the mark further up.  Only the direction from ``butt`` to ``rod``
  is used, so on unmarked footage it can be any point on the lower rod, and
  need not be the same place in every frame.
* Note the frame in which the rod is straight after the stop (RSP, Rod
  Straight Position).  It becomes ``t = 0``.
* Leave the cells of a point empty in frames where it is hidden; those rows
  are skipped.

The table must be a plain comma-separated file with one header row and a
decimal point.  Lines starting with ``#`` are skipped.  Readers for the native
export files of the tracker programs are not included yet.

Track file format
------------------------------
.. code-block:: json

    {
      "name": "My cast",
      "kind": "stroke_tracks",
      "table_csv": "tracks.csv",
      "columns": {"frame": "frame",
                  "butt_x": "butt_x", "butt_y": "butt_y",
                  "rod_x": "rod_x", "rod_y": "rod_y"},
      "fps": 240,
      "units": "px",
      "scale": {"length_m": 0.50, "from_px": [412, 655], "to_px": [478, 502]},
      "y_axis": "down",
      "casting_direction": "right",
      "rsp": {"frame": 152},
      "butt_offset_m": 0.10,
      "tracking_noise": 1.5
    }

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Key
     - Meaning
   * - ``kind``
     - Always ``"stroke_tracks"``.
   * - ``table_csv``
     - The table, relative to the JSON file.
   * - ``columns``
     - The table's column names for ``butt_x``, ``butt_y``, ``rod_x``,
       ``rod_y`` and exactly one of ``frame`` and ``t`` (time in seconds).
       Further points can be named as ``<name>_x`` and ``<name>_y`` pairs, for
       example ``tip_x`` and ``tip_y``; they are kept with the tracks and not
       used for the stroke.
   * - ``fps``
     - Frame rate.  Required when the table has a ``frame`` column.
   * - ``units``
     - ``"px"`` or ``"m"`` (when the tracker program has already calibrated
       the positions).
   * - ``scale``
     - For pixels only: ``{"m_per_px": ...}``, or a known length ``length_m``
       between the pixel points ``from_px`` and ``to_px``.
   * - ``y_axis``
     - ``"down"`` or ``"up"``: the direction in which the table's ``y`` grows.
       Default ``"down"`` for pixels and ``"up"`` for metres.
   * - ``casting_direction``
     - ``"right"`` (default) or ``"left"``: where the cast goes in the table's
       ``x``.
   * - ``rsp``
     - ``{"frame": ...}`` or ``{"t": ...}``: the RSP instant, in the table's
       time base.  It must lie inside the track.
   * - ``butt_offset_m``
     - Distance from the rod butt end to the ``butt`` point (default 0).
   * - ``tracking_noise``
     - How accurately the points are marked: the standard deviation per
       coordinate, in the units of the table.  Optional; it sets the
       smoothing.

Other keys, such as ``description`` and ``source``, are kept as metadata.  A
table needs at least eight usable rows.

Making the stroke
------------------------------
.. code-block:: python

    from flycastsim.fem import save_stroke, simulate_cast1, stroke_from_tracks

    result = stroke_from_tracks("my_cast")       # folder with tracks.json
    print(result.rms_angle_deg, result.rms_hand_m)
    save_stroke(result.stroke, "my_strokes/my_cast")
    cast = simulate_cast1(stroke=result.stroke)

or from the command line::

    uv run python examples/stroke_from_tracks.py --tracks my_cast --out my_strokes/my_cast
    uv run python examples/stroke_from_tracks.py --demo --out demo_stroke

``--demo`` needs no video: it uses synthetic tracks made from the bundled
Cast #1 stroke.  The step 4 notebook
(``examples/notebooks/04_casting_parameters.ipynb``) shows the same with
plots.

The result holds the stroke, the **raw samples** (the angle and hand position
of each tracked frame before smoothing) and the RMS deviation of the stroke
from them.  Plot the raw samples against the stroke to see whether the
smoothing has flattened the stop.  The stroke's metadata records the tracks,
the frame rate, the smoothing and the deviations.

Method
------------------------------
#. The points are brought into the stroke frame: metres, the casting direction
   as :math:`+x` and :math:`+y` up.
#. The rod-butt angle of a frame is the direction from ``butt`` to ``rod``,
   made continuous over time.  The hand position is the ``butt`` point moved
   back along that direction by ``butt_offset_m``.
#. The angle and the two hand coordinates are each fitted over time with a
   cubic smoothing spline [Reinsch1967]_, the usual method for differentiating
   tracked motion data [Woltring1986]_.

   * With a stated tracking noise :math:`\sigma` the spline is the smoothest
     one whose residual equals the noise (Reinsch's criterion).  The noise of
     the angle in a frame is :math:`\sqrt{2}\,\sigma / d`, with :math:`d` the
     distance between the two points.
   * Without a stated noise the smoothing strength is chosen from the data by
     generalised cross-validation [CravenWahba1979]_.
   * ``smoothing=False`` keeps the raw samples as the stroke table.
#. The curves are sampled every 2.5 ms (``dt``), with RSP at :math:`t = 0` and
   the hand at the origin there.  The hand position has no effect on the
   simulated cast; only its velocity has.

Two warnings are given, and the stroke is still returned: when the median
frame interval is more than 10 ms, and when the mean angular speed or hand
speed over the first or last 5 % of the track is more than 20 % of its peak.

How accurate is it?
------------------------------
``examples/stroke_extraction_study.py`` makes synthetic tracks from the bundled
Cast #1 stroke for a grid of frame rates and noise levels, extracts a stroke
from each and runs the simulation with it.  The table compares with the run
that uses the bundled stroke itself, in which the rod chord shortens by
166 mm and the tip deflects by up to 1676 mm.  The tracks are at 3 mm per
pixel with the two points 0.40 m apart and a 0.1 s pause at each end; values
are means over five noise realisations.

.. csv-table::
   :header: "fps", "noise [px]", "angle RMS [deg]", "hand RMS [mm]", "peak ang. speed [%]", "chord [mm]", "tip defl. [mm]", "peak ang. speed, auto [%]", "chord, auto [mm]", "tip defl., auto [mm]"
   :widths: 6, 8, 10, 10, 12, 10, 10, 12, 10, 12

   500, 0, 0.00, 0.00, -0.02, 0.34, 0.84, -0.02, 0.34, 0.84
   500, 0.5, 0.11, 0.65, -7.99, 9.01, 36.93, -3.64, 10.29, 37.33
   500, 1, 0.20, 1.23, -11.00, 14.89, 59.60, -4.80, 15.77, 62.91
   500, 2, 0.37, 2.35, -14.53, 24.87, 115.79, -4.23, 29.86, 119.57
   240, 0, 0.00, 0.00, 0.02, 0.06, 0.59, 0.02, 0.06, 0.59
   240, 0.5, 0.14, 0.96, -9.08, 12.77, 39.53, -3.08, 18.27, 58.54
   240, 1, 0.25, 1.81, -12.02, 20.37, 76.88, -6.32, 21.50, 89.08
   240, 2, 0.45, 3.46, -15.64, 35.54, 139.94, -9.05, 25.45, 111.86
   120, 0, 0.01, 0.00, 0.35, 0.36, 1.24, 0.35, 0.36, 1.24
   120, 0.5, 0.20, 1.32, -11.60, 17.94, 76.88, -7.28, 24.55, 112.55
   120, 1, 0.36, 2.40, -14.63, 28.56, 113.62, -9.43, 34.69, 148.70
   120, 2, 0.65, 4.50, -18.76, 39.93, 217.44, -12.87, 54.00, 229.29
   60, 0, 0.02, 0.02, -0.81, 2.25, 7.00, -0.81, 2.25, 7.00
   60, 0.5, 0.24, 1.61, -11.75, 20.02, 72.11, -8.00, 19.98, 78.66
   60, 1, 0.43, 2.87, -15.01, 30.52, 131.32, -10.33, 27.44, 122.30
   60, 2, 0.78, 5.11, -19.35, 43.82, 212.93, -12.00, 47.24, 203.99
   30, 0, 0.12, 0.14, -10.04, 10.25, 41.84, -10.04, 10.25, 41.84
   30, 0.5, 0.32, 1.78, -13.23, 34.51, 102.94, -9.27, 37.93, 102.26
   30, 1, 0.58, 3.08, -16.14, 49.43, 156.60, -9.47, 54.33, 169.57
   30, 2, 1.05, 5.48, -20.42, 65.31, 263.89, -10.68, 67.74, 271.51

The first five result columns are with the noise stated, the last three with
automatic smoothing.  "Chord" and "tip defl." are the largest differences in
the simulated rod chord length and tip deflection over the cast.

What the study shows:

* **Tracking noise matters more than frame rate.**  Without noise, the frame
  rate costs 0.1 mm of chord at 240, 2 mm at 60 and 10 mm at 30 frames per
  second.  One pixel of noise costs about 20 mm at 240 frames per second.
* **The peak rotation speed comes out low.**  With one pixel of noise the
  smoothing takes 12 % off the peak angular speed (6 % with automatic
  smoothing), and the simulated rod bends less.  The bundled stroke has kinks
  in its angular velocity, which any smoothing clips, so a real stroke should
  lose less.
* **The angle is the weak point.**  Halving the pixel size (1.5 mm per pixel)
  or doubling the distance between the points (0.80 m) each bring the chord
  difference at 240 frames per second and one pixel from 20 mm to about
  13 mm; both together give 8 mm.
* **Stating the noise and automatic smoothing do about equally well** on the
  simulated rod.  Stating the noise is recommended for footage tracked by an
  automatic tracker, whose errors in neighbouring frames are related, which
  misleads the automatic choice.

The study is optimistic: the synthetic rod is straight between the two
points, the noise is independent from frame to frame, and the view is exactly
square.  It has not yet been checked against real footage.

Limits and open items
------------------------------
* **No video reading and no automatic tracking.**  The points come from
  another program.
* **No readers for native tracker export files**; the table must be shaped
  into a plain comma-separated file.
* **Marking points in the app** is planned, using the same track format.
* **One smoothing strength for the whole track** rounds off the stop.  A
  strength that varies over the stroke is a possible improvement.
* **Rod bend between the two points** biases the angle; it is not corrected.
* **The view must be square to the casting plane**; perspective and lens
  distortion are not corrected.
* **RSP is given by the user**, not detected.
* **Validation against real footage** is outstanding.

References
------------------------------
.. [Reinsch1967] C. H. Reinsch, *Smoothing by spline functions*,
   Numer. Math. 10 (1967) 177-183.
.. [CravenWahba1979] P. Craven and G. Wahba, *Smoothing noisy data with spline
   functions*, Numer. Math. 31 (1979) 377-403.
.. [Woltring1986] H. J. Woltring, *A Fortran package for generalized,
   cross-validatory spline smoothing and differentiation*, Adv. Eng. Software
   8 (1986) 104-113.
