"""Zip archives of rod measurement data sets and fitted rods.

Used to upload a measured rod (a folder with ``rod.yaml``, the bend frames
and the frequency CSV, as in ``assets/<ROD>/``) and to download a fitted rod
(``rod.json``, ``rod.csv``, ``fit_summary.json``, ``rod.yaml``), e.g. in the
Streamlit app.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path, PurePosixPath

#: Default limit on the total uncompressed size of an uploaded archive.
MAX_ARCHIVE_BYTES = 500 * 1024 * 1024

#: Files that make up a fitted-rod folder.
FITTED_ROD_FILES = ("rod.json", "rod.csv", "fit_summary.json", "rod.yaml")


def extract_rod_archive(data: bytes, dest: str | Path, *,
                        max_bytes: int = MAX_ARCHIVE_BYTES) -> Path:
    """Extract a zipped rod data set and return the folder with ``rod.yaml``.

    ``rod.yaml`` may sit at the top of the archive or one folder down (a
    zipped ``assets/<ROD>/`` folder).  Members with absolute paths or ``..``
    components are rejected, as are archives whose uncompressed size exceeds
    ``max_bytes``; macOS metadata (``__MACOSX/``) is skipped.

    Raises:
        ValueError: For an unsafe or oversized archive, or one without
            exactly one ``rod.yaml`` within the top two levels.
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        members = [m for m in zf.infolist()
                   if not m.filename.startswith("__MACOSX/")]
        total = sum(m.file_size for m in members)
        if total > max_bytes:
            raise ValueError(f"archive too large ({total / 2**20:.0f} MB "
                             f"uncompressed, limit {max_bytes / 2**20:.0f} MB)")
        for m in members:
            path = PurePosixPath(m.filename)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"unsafe path in archive: {m.filename!r}")
        for m in members:
            zf.extract(m, dest)
    candidates = [p for p in dest.rglob("rod.yaml")
                  if len(p.relative_to(dest).parts) <= 2]
    if len(candidates) != 1:
        raise ValueError("the archive must contain exactly one rod.yaml at "
                         f"its top or one folder down (found "
                         f"{len(candidates)})")
    return candidates[0].parent


def fitted_rod_zip(folder: str | Path, name: str | None = None) -> bytes:
    """Zip a fitted-rod folder (the files in :data:`FITTED_ROD_FILES`).

    Files are stored under ``<name>/`` (default: the folder name).
    """
    folder = Path(folder)
    name = name or folder.name
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in FITTED_ROD_FILES:
            if (folder / fname).exists():
                zf.write(folder / fname, f"{name}/{fname}")
    return buf.getvalue()


def measurement_zip(meas, name: str | None = None) -> bytes:
    """Zip the files of a measurement data set that the fit uses.

    Includes ``rod.yaml``, the frequency CSV, the static-bend frames from
    ``first_frame`` to ``last_frame``, the background frame and the track
    file, if present -- not videos or fit outputs.

    Args:
        meas: A :class:`~flycastsim.rod.measurement.RodMeasurement`.
        name: Top folder in the archive (default: the measurement id).
    """
    root = Path(meas.root)
    name = name or meas.id
    sb = meas.raw.get("static_bend", {})
    files = [root / "rod.yaml", *meas.frame_paths()]
    for rel in (meas.raw.get("frequency_test", {}).get("csv"),
                sb.get("background"), sb.get("track_file")):
        if rel:
            files.append(root / rel)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for path in files:
            if path.exists():
                zf.write(path, f"{name}/{path.relative_to(root).as_posix()}")
    return buf.getvalue()
