"""Example notebooks in ``examples/notebooks`` (``example-notebooks`` spec)."""
import ast
import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK_DIR = ROOT / "examples" / "notebooks"
NOTEBOOKS = sorted(NOTEBOOK_DIR.glob("*.ipynb"))
#: Workflow step number -> notebook stem.
STEP_NOTEBOOKS = {
    1: "01_simple_1d_model",
    2: "02_rod_characteristics",
    3: "03_line_and_leader",
    4: "04_casting_parameters",
    5: "05_simulate_cast",
}
#: Packages needed only to run or test the notebooks.
NOTEBOOK_TOOLS = ("ipykernel", "nbclient")

each_notebook = pytest.mark.parametrize(
    "path", NOTEBOOKS, ids=[p.stem for p in NOTEBOOKS])


def _read(path):
    import nbformat

    return nbformat.read(path, as_version=4)


def _cells(path, cell_type):
    return [c for c in _read(path).cells if c.cell_type == cell_type]


def _headings(path):
    """Markdown heading texts of a notebook, in order."""
    return [line.lstrip("#").strip()
            for cell in _cells(path, "markdown")
            for line in cell.source.splitlines() if line.startswith("#")]


def test_step_notebooks_exist():
    """There is one notebook per workflow step, titled with its step."""
    assert NOTEBOOKS, "no notebooks found"
    for step, stem in STEP_NOTEBOOKS.items():
        path = NOTEBOOK_DIR / f"{stem}.ipynb"
        assert path.is_file(), path
        assert _headings(path)[0].startswith(f"Step {step}:"), path


def test_complete_workflow_covers_steps():
    """The complete workflow has a section for each of steps 2 to 5."""
    headings = _headings(NOTEBOOK_DIR / "complete_workflow.ipynb")
    for step in (2, 3, 4, 5):
        assert any(h.startswith(f"Step {step}:") for h in headings), step


@each_notebook
def test_notebook_executes(path):
    """The notebook runs top to bottom in a fresh kernel."""
    from nbclient import NotebookClient

    client = NotebookClient(_read(path), timeout=300, kernel_name="python3",
                            resources={"metadata": {"path": str(path.parent)}})
    client.execute()


@each_notebook
def test_notebook_imports_only_public_api(path):
    """No ``flycastsim`` module or name with a leading underscore."""
    imports = set()
    for cell in _cells(path, "code"):
        for node in ast.walk(ast.parse(cell.source)):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [f"{node.module}.{a.name}" for a in node.names]
            else:
                continue
            imports.update(n for n in names
                           if n.split(".")[0] == "flycastsim")
    assert imports, path
    assert not {n for n in imports
                if any(part.startswith("_") for part in n.split("."))}


@each_notebook
def test_notebook_has_no_outputs(path):
    """Notebooks are committed with outputs and counts cleared."""
    for cell in _cells(path, "code"):
        assert not cell.outputs, path
        assert cell.execution_count is None, path


def test_notebook_tools_not_in_app_requirements():
    """The notebook tools are not installed in the Streamlit deployment."""
    pinned = {re.split(r"[=<>!~\[; ]", line, maxsplit=1)[0].lower()
              for line in (ROOT / "requirements.txt").read_text().splitlines()
              if line and not line.startswith(("#", " "))}
    assert "streamlit" in pinned
    groups = tomllib.loads(
        (ROOT / "pyproject.toml").read_text())["dependency-groups"]
    app = " ".join(groups["app"]).lower()
    for tool in NOTEBOOK_TOOLS:
        assert tool not in pinned
        assert tool not in app
        assert any(dep.lower().startswith(tool) for dep in groups["dev"])
    for name in ("streamlit_app.py", "rod_profile_pages.py"):
        tree = ast.parse((ROOT / name).read_text(encoding="utf-8"))
        modules = {alias.name.split(".")[0] for node in ast.walk(tree)
                   if isinstance(node, ast.Import) for alias in node.names}
        modules |= {node.module.split(".")[0] for node in ast.walk(tree)
                    if isinstance(node, ast.ImportFrom) and node.module}
        assert not modules & set(NOTEBOOK_TOOLS), name
