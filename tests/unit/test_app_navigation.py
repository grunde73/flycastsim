"""App sections and the cast-section switch (``app-navigation`` spec)."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SWITCH = "FLYCASTSIM_SHOW_CAST"
CAST = "Sample fly cast"


def _app(monkeypatch, switch=None):
    """Run the app with the switch unset (``None``) or set to ``switch``."""
    from streamlit.testing.v1 import AppTest

    monkeypatch.syspath_prepend(str(ROOT))
    monkeypatch.chdir(ROOT)
    if switch is None:
        monkeypatch.delenv(SWITCH, raising=False)
    else:
        monkeypatch.setenv(SWITCH, switch)
    return AppTest.from_file(str(ROOT / "streamlit_app.py"),
                             default_timeout=60).run()


def _sections(app):
    """Section labels as shown in the sidebar selector."""
    return list(app.sidebar.selectbox[0].options)


def _text(app):
    """All markdown-like text on the page."""
    parts = [m.value for m in app.markdown]
    parts += [e.value for kind in ("info", "warning", "success", "caption")
              for e in getattr(app, kind)]
    return "\n".join(parts)


def test_default_sections_hide_cast(monkeypatch):
    """Without the switch only the three finished sections are offered."""
    app = _app(monkeypatch)
    assert not app.exception
    assert _sections(app) == ["Introduction", "Simple 1D model",
                              "Rod parameters"]


def test_cast_switch_shows_cast_section(monkeypatch):
    """With the switch on the cast section is last and renders."""
    app = _app(monkeypatch, "1")
    assert _sections(app) == ["Introduction", "Simple 1D model",
                              "Rod parameters", CAST]
    app.sidebar.selectbox[0].set_value((CAST, 2)).run()
    assert not app.exception
    assert "Cast #1" in _text(app)
    # The page waits for "Run simulation"; no simulation runs here.
    assert "Run simulation" in _text(app)


@pytest.mark.parametrize("value, shown", [
    ("true", True), ("YES", True), ("on", True), (" 1 ", True),
    ("0", False), ("false", False), ("", False), ("maybe", False),
])
def test_cast_switch_values(value, shown, monkeypatch):
    """Only 1/true/yes/on (any letter case) turn the section on."""
    monkeypatch.syspath_prepend(str(ROOT))
    from rod_profile_pages import cast_page_enabled

    monkeypatch.setenv(SWITCH, value)
    assert cast_page_enabled() is shown
    monkeypatch.delenv(SWITCH)
    assert cast_page_enabled() is False


@pytest.mark.parametrize("switch", [None, "1"])
def test_intro_presents_workflow(switch, monkeypatch):
    """The Introduction lists the five steps and what is available."""
    text = _text(_app(monkeypatch, switch))
    for step in ("Simple 1-D model", "Rod characteristics",
                 "Line and leader characteristics", "Casting parameters",
                 "Simulate a fly cast"):
        assert step in text
    not_yet = text.count("Not yet available in this app.")
    if switch is None:
        assert not_yet == 3
    else:
        assert not_yet == 2
        assert f"Available in **{CAST}**" in text


def test_hidden_cast_is_not_mentioned(monkeypatch):
    """With the switch off no visible page points at the cast section."""
    app = _app(monkeypatch)
    assert CAST.lower() not in _text(app).lower()
    app.sidebar.selectbox[0].set_value(("Rod parameters", 3)).run()
    app.radio(key="rod_view").set_value("Stiffness profiles").run()
    assert not app.exception
    text = _text(app)
    assert "Stiffness profiles" in text
    assert CAST.lower() not in text.lower()
