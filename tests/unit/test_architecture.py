# -*- coding: utf-8 -*-
"""Tests for the project constraints in ``openspec/specs/architecture``."""
import ast
import subprocess
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
APP_FILES = ["streamlit_app.py", "rod_profile_pages.py"]
# Private imports the app still relies on; do not add to this list.
KNOWN_PRIVATE_IMPORTS = {"flycastsim.fem._cast1_data"}


def _flycastsim_imports(path):
    """Yield the dotted name of every ``flycastsim`` import in ``path``."""
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [f"{node.module}.{alias.name}" for alias in node.names]
        else:
            continue
        yield from (n for n in names if n.split(".")[0] == "flycastsim")


@pytest.mark.parametrize("name", APP_FILES)
def test_app_imports_only_public_api(name):
    imports = set(_flycastsim_imports(ROOT / name))
    assert imports, name
    private = {n for n in imports
               if any(part.startswith("_") for part in n.split("."))}
    assert private <= KNOWN_PRIVATE_IMPORTS


def test_wheel_ships_bundled_data(tmp_path):
    subprocess.run(["uv", "build", "--wheel", "--quiet",
                    "--out-dir", str(tmp_path)], cwd=ROOT, check=True)
    wheel = next(tmp_path.glob("*.whl"))
    with zipfile.ZipFile(wheel) as zf:
        shipped = set(zf.namelist())
    src = ROOT / "src"
    expected = {p.relative_to(src).as_posix()
                for suffix in ("*.json", "*.csv")
                for p in (src / "flycastsim" / "data").rglob(suffix)}
    assert expected
    assert expected <= shipped
