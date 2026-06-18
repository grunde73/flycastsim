"""Reynolds-number air-drag laws for the fly-casting continuum model.

This module implements the aerodynamic drag the line/leader experience as they
move through air -- the first of the two model extensions described by Ekander,
Perkins & Richards (2025), *Sports Engineering*.

The drag force per unit length is split into a **normal** component
``f_n,drag`` (eq 5) and a **tangential** component ``f_s,drag`` (eq 6), each the
sum of a *form-drag* term (quadratic in velocity) and a *friction-drag* term
whose coefficient follows a Reynolds-number power law.  With ``u`` the local
relative air velocity, ``d`` the outer diameter, ``rho`` the air density and
``mu`` the dynamic viscosity, the section Reynolds number is
``Re = rho * |u| * d / mu``.

Normal (eq 5), constants ``zeta_n0 = 1.0``, ``zeta_n = 10``, ``m_n = -0.75``::

    f_n = zeta_n0 * d * rho * |u_n| * u_n / 2
        + zeta_n * (rho * d / mu) ** m_n * d * 0.5 * rho * |u_n| ** (1 + m_n) * u_n

Tangential (eq 6), constants ``zeta_s0 = 0.0022``, ``zeta_s = 2.0``,
``m_s = -0.91``::

    f_s = zeta_s0 * pi * d * (rho / 2) * |u_s| * u_s
        + zeta_s * (rho * d / mu) ** m_s * pi * d * 0.5 * rho * |u_s| ** (1 + m_s) * u_s

Both expressions are odd in the velocity, so each force shares the sign of its
velocity component.  The momentum residual in :func:`flycastsim.fem.operators.residual`
adds ``f_drag`` on the *force* side, which makes the resulting acceleration
oppose the motion -- i.e. the drag is dissipative.
"""

from __future__ import annotations

import numpy as np

__all__ = ["reynolds_drag", "RHO_AIR", "MU_AIR"]

#: Default air density [kg/m^3].
RHO_AIR = 1.2
#: Default air dynamic viscosity [N s/m^2].
MU_AIR = 1.8e-5

# Published drag-law constants (paper eqs 5 and 6).
_ZETA_N0 = 1.0
_ZETA_N = 10.0
_M_N = -0.75
_ZETA_S0 = 0.0022
_ZETA_S = 2.0
_M_S = -0.91


def reynolds_drag(dom, *, rho_air: float = RHO_AIR, mu_air: float = MU_AIR,
                  zeta_n0: float = _ZETA_N0, zeta_n: float = _ZETA_N,
                  m_n: float = _M_N, zeta_s0: float = _ZETA_S0,
                  zeta_s: float = _ZETA_S, m_s: float = _M_S,
                  u_eps: float = 1.0e-6):
    """Build an ``f_drag`` callable implementing the Reynolds drag laws.

    Args:
        dom: The :class:`~flycastsim.fem.domain.Subdomain`; its outer-diameter
            profile ``dom.d`` [m] sets the drag magnitude (zero diameter gives
            zero drag).
        rho_air: Air density [kg/m^3].
        mu_air: Air dynamic viscosity [N s/m^2].
        zeta_n0, zeta_n, m_n: Normal-drag form/friction coefficients and
            Reynolds exponent (eq 5).
        zeta_s0, zeta_s, m_s: Tangential-drag form/friction coefficients and
            Reynolds exponent (eq 6).
        u_eps: Small velocity floor [m/s] used inside the ``|u| ** (1 + m)``
            friction terms to keep them finite and smooth as ``u -> 0`` (the
            exponent ``1 + m`` is fractional and ``m < 0``).

    Returns:
        A callable ``f_drag(fields) -> (f_s, f_n)`` returning the tangential
        and normal drag force per unit length as node-length arrays (same sign
        as the corresponding velocity component, so the force opposes motion
        once moved to the acceleration side of the momentum balance).
    """
    d = np.asarray(dom.d, dtype=float)
    # Reynolds-number prefactor (rho * d / mu) raised to the law exponents.
    re_coef = rho_air * d / mu_air
    # Guard against zero-diameter nodes so 0 ** (negative) does not blow up;
    # those nodes carry no drag anyway because of the leading ``d`` factor.
    re_safe = np.where(d > 0.0, re_coef, 1.0)
    fric_n = zeta_n * np.power(re_safe, m_n) * d * 0.5 * rho_air
    fric_s = zeta_s * np.power(re_safe, m_s) * np.pi * d * 0.5 * rho_air
    form_n = zeta_n0 * d * rho_air / 2.0
    form_s = zeta_s0 * np.pi * d * (rho_air / 2.0)

    def f_drag(fields):
        u_s = np.asarray(fields.u_s, dtype=float)
        u_n = np.asarray(fields.u_n, dtype=float)

        abs_s = np.hypot(np.abs(u_s), u_eps)
        abs_n = np.hypot(np.abs(u_n), u_eps)

        f_s = form_s * np.abs(u_s) * u_s \
            + fric_s * np.power(abs_s, 1.0 + m_s) * u_s
        f_n = form_n * np.abs(u_n) * u_n \
            + fric_n * np.power(abs_n, 1.0 + m_n) * u_n
        return f_s, f_n

    return f_drag
