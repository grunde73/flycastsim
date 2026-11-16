# stroke-extraction Specification

## Purpose
Turns points tracked in a video of a cast into a casting stroke that can drive
the simulation. Covers the track file format, loading and saving tracks, the
conversion from tracks to a stroke, the warnings about tracks that cannot give
a reliable stroke, and synthetic tracks made from a known stroke.

## Requirements
### Requirement: Track file format
Tracks SHALL be stored as a JSON metadata file plus a CSV table. The JSON SHALL have `"kind": "stroke_tracks"`, a `name`, a `table_csv` path relative to the JSON file, `units` (`px` or `m`), an `rsp` entry, and a `columns` mapping that names the CSV columns `butt_x`, `butt_y`, `rod_x`, `rod_y` and exactly one of `t` [s] or `frame`. A table indexed by `frame` SHALL also give `fps`. Other JSON keys SHALL be kept as metadata.

#### Scenario: Tracks indexed by frame
- **WHEN** a track file with a frame column, `fps` and the four point columns is loaded
- **THEN** the loaded tracks hold the point positions, the time of each row as frame divided by `fps`, and the metadata from the JSON (`tests/unit/test_fem_tracks.py::test_load_tracks_reads_table_and_metadata`)

#### Scenario: Tracks indexed by time
- **WHEN** a track file with a time column and no `fps` is loaded
- **THEN** the loaded tracks use the time column as given (`test_fem_tracks.py::test_load_tracks_with_time_column`)

### Requirement: Tracked points
The `butt` point SHALL be a point on the rod at or near the rod butt, and the `rod` point a point further up the rod on the stiff butt section. The `rod` point MAY be a different place on the rod in each row. The optional `butt_offset_m` SHALL be the distance from the rod butt end to the `butt` point, and SHALL default to zero. The `columns` mapping MAY name further points as `<name>_x` and `<name>_y` pairs; these SHALL be kept with the tracks and SHALL NOT affect the stroke.

#### Scenario: Extra point is kept and ignored
- **WHEN** tracks with an extra `tip` point are loaded and converted
- **THEN** the tracks hold the `tip` positions, and the stroke equals the one from the same tracks without `tip` (`test_fem_tracks.py::test_extra_points_kept_and_ignored`)

### Requirement: Track calibration and orientation
Tracks in `px` SHALL give a `scale`, either as `m_per_px` or as a known length `length_m` between two stated pixel points. Tracks in `m` SHALL need no scale. `y_axis` SHALL say whether the table's `y` grows `down` or `up`, defaulting to `down` for `px` and `up` for `m`. `casting_direction` SHALL say whether the cast goes to the `right` or `left` in the table's `x`, defaulting to `right`.

#### Scenario: Scale from a known length
- **WHEN** tracks in pixels give a known length between two pixel points
- **THEN** the conversion uses the length divided by the pixel distance as metres per pixel (`test_fem_tracks.py::test_scale_from_known_length`)

#### Scenario: Image coordinates and a cast to the left
- **WHEN** the same cast is given once in metres with `y` up and the cast to the right, and once in pixels with `y` down and the cast to the left
- **THEN** both give the same stroke (`test_fem_tracks.py::test_orientation_and_units_give_same_stroke`)

### Requirement: Rows with missing points are skipped
A row of the track table in which a `butt` or `rod` value is empty SHALL be skipped, so that frames where a point is hidden can be left blank. The rows that remain need not be evenly spaced in time.

#### Scenario: Hidden point in some frames
- **WHEN** a track table has empty `rod` values in some rows
- **THEN** the tracks load without those rows and convert to a stroke (`test_fem_tracks.py::test_rows_with_missing_points_are_skipped`)

### Requirement: Invalid track files are rejected
Loading tracks SHALL fail with a `ValueError` that names the problem when the `kind` is not `stroke_tracks`, a required key or mapped column is missing, both or neither of `t` and `frame` are mapped, `fps` is missing or not positive for a frame table, `units` is unknown, a pixel table has no valid scale, a value is not a finite number, the times are not strictly increasing, or fewer than eight rows remain. A missing file SHALL fail with `FileNotFoundError`.

#### Scenario: Malformed track files
- **WHEN** a track file has one of the listed problems
- **THEN** loading fails with a `ValueError` (`test_fem_tracks.py::test_load_tracks_rejects_invalid`, parametrised over the listed problems)

#### Scenario: Missing file
- **WHEN** the track source does not exist
- **THEN** loading fails with a `FileNotFoundError` (`test_fem_tracks.py::test_load_tracks_missing_file`)

### Requirement: Tracks can be saved
The library SHALL write tracks to a folder as a JSON file plus a CSV table in the track file format. Loading the written files SHALL give back the same times, point positions, settings, name and metadata.

#### Scenario: Round trip
- **WHEN** tracks are saved and loaded again
- **THEN** the loaded tracks equal the original in their table values, settings, name and metadata (`test_fem_tracks.py::test_save_tracks_round_trip`)

### Requirement: Stroke time is relative to RSP
The `rsp` entry SHALL give the RSP instant as a `frame` or a time `t` in the table's time base. The stroke's time SHALL be the track time minus the RSP time, so RSP is `t = 0`. The conversion SHALL fail with a `ValueError` when RSP lies outside the time range of the track.

#### Scenario: RSP inside the track
- **WHEN** tracks with RSP at a frame inside the table are converted
- **THEN** the stroke's time range starts before zero and ends after zero, offset by the RSP time (`test_fem_tracks.py::test_stroke_time_is_relative_to_rsp`)

#### Scenario: RSP outside the track
- **WHEN** the RSP frame is before the first or after the last row
- **THEN** the conversion fails with a `ValueError` (`test_fem_tracks.py::test_rsp_outside_track_is_rejected`)

### Requirement: Stroke angle from the tracked points
The stroke's rod-butt angle SHALL be the direction from the `butt` point to the `rod` point, in the conventions of the `cast-stroke` capability: the casting direction is `+x`, `+y` is up, 0 degrees is level forward and 90 degrees is straight up. The angle SHALL be continuous over the track, without jumps of 360 degrees. The conversion SHALL fail with a `ValueError` when the two points coincide in a row.

#### Scenario: Angle of a known rod direction
- **WHEN** tracks are made with the rod pointing in known directions, including a sweep through 180 degrees
- **THEN** the stroke's angle at those times equals the known directions and is continuous (`test_fem_tracks.py::test_angle_from_points`)

#### Scenario: Coincident points
- **WHEN** a row has the `butt` and `rod` points at the same position
- **THEN** the conversion fails with a `ValueError` (`test_fem_tracks.py::test_coincident_points_are_rejected`)

### Requirement: Hand path at the rod butt end
The stroke's hand position SHALL be the position of the rod butt end in metres: the `butt` point moved back along the rod direction by `butt_offset_m`. The hand position SHALL be zero in `x` and `y` at RSP.

#### Scenario: Butt point away from the butt end
- **WHEN** the same cast is tracked once at the butt end and once at a point 0.10 m up the rod with `butt_offset_m` set to 0.10
- **THEN** both give the same hand path (`test_fem_tracks.py::test_butt_offset_is_corrected`)

#### Scenario: Origin at RSP
- **WHEN** any tracks are converted
- **THEN** the stroke's hand position at `t = 0` is zero (`test_fem_tracks.py::test_hand_origin_at_rsp`)

### Requirement: Smoothing set by the tracking noise
The conversion SHALL smooth the angle and the hand path over time. When a tracking noise is stated, as an argument or as `tracking_noise` in the track file, in the units of the table, the smoothing SHALL be as strong as that noise allows: the smoothed hand path SHALL deviate from the raw hand samples by about the stated noise. A stated noise that is not positive SHALL fail with a `ValueError`.

#### Scenario: Residual matches the stated noise
- **WHEN** synthetic tracks with a known noise are converted with that noise stated
- **THEN** the RMS deviation of the smoothed hand path from the raw samples is between 0.7 and 1.3 times the noise (`test_fem_tracks.py::test_residual_matches_stated_noise`)

#### Scenario: More stated noise gives a smoother stroke
- **WHEN** the same noisy tracks are converted with a small and a large stated noise
- **THEN** the larger noise gives the smaller peak angular acceleration (`test_fem_tracks.py::test_more_noise_gives_smoother_stroke`)

### Requirement: Automatic smoothing and no smoothing
When no tracking noise is stated, the conversion SHALL choose the smoothing strength from the data. The caller SHALL be able to switch smoothing off; the stroke table SHALL then hold the raw samples at the track's own times.

#### Scenario: Automatic smoothing reduces the error
- **WHEN** noisy synthetic tracks are converted without a stated noise
- **THEN** the stroke's angle is closer to the true angle than the raw samples are (`test_fem_tracks.py::test_automatic_smoothing_reduces_error`)

#### Scenario: Smoothing off
- **WHEN** tracks are converted with smoothing off
- **THEN** the stroke's times, angles and hand positions equal the raw samples (`test_fem_tracks.py::test_smoothing_off_keeps_raw_samples`)

### Requirement: Smoothed strokes are sampled densely
With smoothing on, the stroke table SHALL sample the smoothed curves at a fixed time step, 2.5 ms unless the caller gives another, from the first to the last track time, and SHALL include `t = 0`. Loading the saved stroke SHALL NOT give the coarse-sampling warning of the `cast-stroke` capability.

#### Scenario: Default time step
- **WHEN** tracks filmed at 60 frames per second are converted with the default settings
- **THEN** the stroke table has a 2.5 ms step, contains `t = 0`, and loads from its saved files without a coarse-sampling warning (`test_fem_tracks.py::test_smoothed_stroke_is_dense`)

### Requirement: Conversion reports the raw samples and the fit
The conversion SHALL return, with the stroke, the raw angle and hand samples at the track times in the stroke's frame and units, and the RMS deviation of the smoothed angle [deg] and hand path [m] from them, so that a caller can judge whether the smoothing has flattened the stroke.

#### Scenario: Raw samples and residuals are returned
- **WHEN** tracks are converted
- **THEN** the result holds the stroke, raw samples with one entry per track row, and RMS deviations that equal those computed from the stroke and the raw samples (`test_fem_tracks.py::test_result_reports_raw_samples_and_fit`)

### Requirement: Extracted strokes record how they were made
The metadata of an extracted stroke SHALL state that it was made from tracks, and give the name of the tracks, the number of samples used, the median time step of the track, the smoothing method, the tracking noise used or that it was chosen automatically, the RMS deviations, the scale, and `butt_offset_m`. The metadata SHALL survive saving and loading the stroke.

#### Scenario: Metadata of an extracted stroke
- **WHEN** an extracted stroke is saved and loaded
- **THEN** its metadata holds the listed entries (`test_fem_tracks.py::test_extracted_stroke_metadata`)

### Requirement: Coarse tracks give a warning
The conversion SHALL give a `UserWarning` when the median time step of the track is more than 10 ms, saying that the stop of the stroke may not be resolved at that frame rate. The stroke SHALL still be returned.

#### Scenario: Track at 30 frames per second
- **WHEN** tracks filmed at 30 frames per second are converted
- **THEN** a `UserWarning` about the frame rate is given and a stroke is returned (`test_fem_tracks.py::test_coarse_track_warns`)

#### Scenario: Track at 240 frames per second
- **WHEN** tracks filmed at 240 frames per second, starting and ending at rest, are converted
- **THEN** no warning is given (`test_fem_tracks.py::test_fine_track_at_rest_does_not_warn`)

### Requirement: Tracks that start or end in motion give a warning
The conversion SHALL give a `UserWarning` when the mean angular speed over the first or the last 5 % of the track's duration is more than 20 % of the peak angular speed over the track, or the mean hand speed there is more than 20 % of the peak hand speed. The warning SHALL say which end and which quantity, because the simulation starts from rest and holds the stroke's end values. The stroke SHALL still be returned.

#### Scenario: Track cut off mid-stroke
- **WHEN** tracks that end while the rod is still rotating fast are converted
- **THEN** a `UserWarning` naming the end of the track and the angle is given (`test_fem_tracks.py::test_track_ending_in_motion_warns`)

#### Scenario: Noisy track with a pause at each end
- **WHEN** tracks with 1 pixel of noise and a 0.1 s pause before and after the stroke are converted
- **THEN** no warning about motion at the ends is given (`test_fem_tracks.py::test_noisy_track_with_pauses_does_not_warn`)

### Requirement: Synthetic tracks from a stroke
The library SHALL make tracks from a stroke, for a given frame rate, scale, units, orientation, distance of the `rod` point from the `butt` point, `butt_offset_m`, a pause filmed before and after the stroke, and Gaussian tracking noise with a seed. The rod SHALL be taken as straight between the two points. Without noise, converting the tracks with smoothing off SHALL give back the stroke's angle and its hand path relative to RSP at the track times.

#### Scenario: Noise-free round trip
- **WHEN** noise-free tracks are made from the bundled Cast #1 stroke and converted with smoothing off
- **THEN** the angle agrees within 0.001 degrees and the hand path, relative to RSP, within 0.01 mm (`test_fem_tracks.py::test_synthetic_tracks_round_trip`)

#### Scenario: Same seed, same tracks
- **WHEN** noisy tracks are made twice with the same seed
- **THEN** the two sets of tracks are identical (`test_fem_tracks.py::test_synthetic_tracks_are_reproducible`)

### Requirement: Extraction recovers a known stroke
For tracks made from the bundled Cast #1 stroke at 240 frames per second and 3 mm per pixel, with the `rod` point 0.40 m from the `butt` point, the default conversion SHALL recover the stroke. Without noise the angle SHALL agree within 0.2 degrees and the hand path within 1 mm at every table time. With 1 pixel of noise and that noise stated, the RMS error SHALL be at most 0.5 degrees in angle and 3 mm in hand position.

#### Scenario: Noise-free tracks
- **WHEN** the noise-free tracks are converted with the default settings
- **THEN** the angle and hand path agree with the bundled stroke within the stated limits (`test_fem_tracks.py::test_recovers_cast1_without_noise`)

#### Scenario: Tracks with one pixel of noise
- **WHEN** the noisy tracks are converted with the noise stated, for each of several seeds
- **THEN** the RMS errors are within the stated limits (`test_fem_tracks.py::test_recovers_cast1_with_noise`)
