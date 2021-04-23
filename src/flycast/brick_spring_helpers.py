"""
Helper functions to deal with data from brick-spring-car
modelling.
"""
import numpy as np
from plotly.subplots import make_subplots
import plotly.graph_objects as go


def plot_brick_spring(df, plot_cols):
    """Helper function to plot brick-spring-car
    simulation data
    """
    col_groups = []
    col_groups.append(([_c for _c in plot_cols if _c.endswith("position") or
                         _c.endswith("ext")], "Position [m]"))
    col_groups.append(([_c for _c in plot_cols if _c.endswith("speed")],
                       "Speed [m/s]"))
    col_groups.append(([_c for _c in plot_cols if _c.endswith("energy")],
                       "Energy [J]"))
    col_groups.append(([_c for _c in plot_cols if _c.endswith("force")],
                       "Force [N]"))
    col_groups.append(([_c for _c in plot_cols if _c.endswith("power")],
                       "Power [W]"))
    col_groups = [_c for _c in col_groups if len(_c[0]) > 0]


    fig = make_subplots(rows=len(col_groups), cols=1, shared_xaxes=True,
                        x_title=r"$time\ [s]$")

    for _i, _c in enumerate(col_groups):
        for _c_col in _c[0]:
            _c_go = go.Scatter(x=df.index, y=np.array(df[_c_col]), name=_c_col)
            fig.add_trace(_c_go, col=1, row=_i + 1)
        fig.update_yaxes(title_text=_c[1], row=_i + 1, col=1)
    return fig


class BrickSpringAnim():
    """Iterator class delivering images for animation
    one image pr. row in the dataframe"""

    def __init__(self, df):
        self.data = df
        pass