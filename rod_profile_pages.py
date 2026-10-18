"""Streamlit views for fitted rod stiffness / mass profiles.

Used by ``streamlit_app.py`` (*Rod parameters* section).  All computation
lives in :mod:`flycastsim.rod`; this module only lays out widgets and plots.
Rods fitted in the app are kept for the session in
``st.session_state["session_rods"]`` (key -> fitted-rod folder) so the
comparison view and the Cast #1 rod selector can use them.
"""
from __future__ import annotations

import streamlit as st

from flycastsim.rod import FittedRod, load_fitted_rods


@st.cache_resource
def bundled_fitted_rods() -> dict[str, FittedRod]:
    """The fitted rods shipped with the package, by id."""
    return {rod.id: rod for rod in load_fitted_rods()}


def available_fitted_rods() -> dict[str, FittedRod]:
    """Bundled fitted rods plus rods fitted in this session.

    Keys are ``"bundled:<id>"`` and ``"session:<id>"``.
    """
    rods = {f"bundled:{k}": v for k, v in bundled_fitted_rods().items()}
    for key, folder in st.session_state.get("session_rods", {}).items():
        rods[key] = FittedRod.from_folder(folder)
    return rods


def rod_label(key: str, rod: FittedRod) -> str:
    """Display name of a fitted rod in selectors."""
    where = "fitted" if key.startswith("bundled:") else "fitted this session"
    return f"{rod.id} — {rod.label.removesuffix(' - fitted rod')} ({where})"
