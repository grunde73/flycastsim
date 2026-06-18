"""
Helper functions to deal with data from brick-spring-car
modelling.
"""
import numpy as np
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import os

from PIL import Image, ImageDraw, ImageFont


_c_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)))
_updir = os.path.split(_c_dir)[0]
FONT_FILE = os.path.join(_updir, 'Open_Sans', 'OpenSans-Regular.ttf')


def _group_columns(plot_cols):
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
    return col_groups


def _resolve_column(df, name):
    """Return the column in ``df`` matching ``name`` exactly or by suffix.

    The default/baseline run renames columns with a "base " prefix, so match
    by suffix to support both base and non-base result frames. An exact match
    is preferred so that, in an overlaid (base + current) frame, the current
    run's column wins. Returns ``None`` if no matching column is found.
    """
    if name in df.columns:
        return name
    for _c in df.columns:
        if _c.endswith(name):
            return _c
    return None


def _event_times(df):
    """Times of key events in a brick-spring-car result frame.

    Returns a dict mapping a human-readable event label to the time (the index
    value) at which it occurs. Missing columns are skipped.
    """
    events = {}
    _car_speed = _resolve_column(df, "car speed")
    if _car_speed is not None:
        events["car max speed"] = df[_car_speed].idxmax()
    _spring_ext = _resolve_column(df, "spring ext")
    if _spring_ext is not None:
        events["spring max ext"] = df[_spring_ext].idxmax()
    return events


def plot_brick_spring(df, plot_cols, mark_events=True):
    """Helper function to plot brick-spring-car
    simulation data
    """
    col_groups = _group_columns(plot_cols)

    fig = make_subplots(rows=len(col_groups), cols=1, shared_xaxes=True,
                        x_title="time [s]")

    for _i, _c in enumerate(col_groups):
        for _c_col in _c[0]:
            _c_go = go.Scatter(x=df.index, y=np.array(df[_c_col]), name=_c_col)
            fig.add_trace(_c_go, col=1, row=_i + 1)
        fig.update_yaxes(title_text=_c[1], row=_i + 1, col=1)

    if mark_events:
        _event_styles = {
            "car max speed": dict(dash="dash", color="orange"),
            "spring max ext": dict(dash="dot", color="purple"),
        }
        for _label, _t in _event_times(df).items():
            _style = _event_styles.get(_label, {})
            # Vertical guide line spanning all (shared-x) subplots
            fig.add_vline(x=_t, line_dash=_style.get("dash"),
                          line_color=_style.get("color"))
            # Legend-only trace so the event label sits with the other labels
            fig.add_trace(go.Scatter(
                x=[None], y=[None], mode="lines",
                line=dict(dash=_style.get("dash"),
                          color=_style.get("color")),
                name="%s (t=%.2f s)" % (_label, float(_t))))
    return fig


def _zigzag(x0, x1, y_center, amplitude, n_coils=12):
    """Return (x, y) arrays for a zig-zag spring between x0 and x1."""
    xs = np.linspace(x0, x1, 2 * n_coils + 1)
    ys = np.full_like(xs, y_center)
    # Alternate up/down for the interior points, keep ends on the centre line
    ys[1:-1:2] = y_center + amplitude
    ys[2:-1:2] = y_center - amplitude
    return xs, ys


def animate_brick_spring(df, n_frames=120, brick_w=0.25, brick_h=0.25,
                         car_w=0.6, car_h=0.4, car_gap=0.5, frame_ms=40):
    """Build a Plotly animation of the brick-spring-car system.

    The whole animation is rendered client-side in the browser, so it is far
    smoother than streaming server-rendered images frame by frame. A play/pause
    button and a slider let the user scrub through the simulation.

    Args:
        df: DataFrame returned by ``brick_spring_simple`` (time-indexed with
            ``brick position``, ``car position`` and ``spring ext`` columns).
        n_frames: Number of animation frames (the data is down-sampled to this
            many frames to keep the figure light).
        brick_w, brick_h: Brick rectangle size in metres.
        car_w, car_h: Car rectangle size in metres.
        car_gap: Constant visual gap between brick and car (metres) so the
            spring always has a visible length.
        frame_ms: Milliseconds per frame during playback.

    Returns:
        plotly.graph_objects.Figure
    """
    def _col(name):
        _resolved = _resolve_column(df, name)
        if _resolved is None:
            raise KeyError(name)
        return np.asarray(df[_resolved])

    brick_pos = _col("brick position")
    car_pos = _col("car position")
    brick_speed = _col("brick speed")
    times = np.asarray(df.index)

    # Times of the key events to highlight during playback
    events = _event_times(df)

    # Down-sample to keep the figure small and playback smooth
    n_rows = len(df)
    step = max(1, n_rows // n_frames)
    idx = np.arange(0, n_rows, step)

    ground_y = 0.0
    spring_y = ground_y + brick_h / 2.0
    spring_amp = brick_h / 3.0

    # --- Release phase --------------------------------------------------
    # When the simulation ends the brick is "let go": the car (and spring)
    # disappear and the brick keeps travelling at its final constant speed.
    t_end = float(times[-1])
    x_brick_end = float(brick_pos[-1])
    v_brick_end = float(brick_speed[-1])

    n_release = max(1, len(idx) // 3)          # ~1/3 extra frames
    dt_frame = (t_end - float(times[0])) / max(1, len(idx))
    release_times = t_end + dt_frame * np.arange(1, n_release + 1)
    release_brick_x = x_brick_end + v_brick_end * (release_times - t_end)

    def _brick_xy_at(x0):
        return ([x0, x0 + brick_w, x0 + brick_w, x0, x0],
                [ground_y, ground_y, ground_y + brick_h,
                 ground_y + brick_h, ground_y])

    def _car_xy(i):
        x0 = car_pos[i] + car_gap
        return ([x0, x0 + car_w, x0 + car_w, x0, x0],
                [ground_y, ground_y, ground_y + car_h,
                 ground_y + car_h, ground_y])

    def _wheels_xy(i):
        x0 = car_pos[i] + car_gap
        return ([x0 + car_w * 0.25, x0 + car_w * 0.75],
                [ground_y, ground_y])

    def _spring_xy(i):
        x_start = brick_pos[i] + brick_w
        x_end = car_pos[i] + car_gap
        return _zigzag(x_start, x_end, spring_y, spring_amp)

    line0 = dict(color="#1f77b4", width=3)
    line_car = dict(color="#d62728", width=3)
    line_spring = dict(color="#2ca02c", width=2)
    marker_wheel = dict(color="black", size=14)

    def _make_traces(bx, by, sx, sy, cx, cy, wx, wy):
        return [
            go.Scatter(x=bx, y=by, mode="lines", fill="toself",
                       line=line0, name="brick", showlegend=False),
            go.Scatter(x=sx, y=sy, mode="lines",
                       line=line_spring, name="spring", showlegend=False),
            go.Scatter(x=cx, y=cy, mode="lines", fill="toself",
                       line=line_car, name="car", showlegend=False),
            go.Scatter(x=wx, y=wy, mode="markers",
                       marker=marker_wheel, name="wheels", showlegend=False),
        ]

    def _traces(i):
        bx, by = _brick_xy_at(brick_pos[i])
        cx, cy = _car_xy(i)
        wx, wy = _wheels_xy(i)
        sx, sy = _spring_xy(i)
        return _make_traces(bx, by, sx, sy, cx, cy, wx, wy)

    def _release_traces(x0):
        # Brick only; car, spring and wheels are hidden (empty traces).
        bx, by = _brick_xy_at(x0)
        return _make_traces(bx, by, [], [], [], [], [], [])

    # Fixed axis ranges so nothing jumps around during playback
    x_min = float(brick_pos.min()) - 0.5
    x_max = max(float(car_pos.max()) + car_gap + car_w,
                float(release_brick_x.max()) + brick_w) + 0.5
    y_max = ground_y + max(brick_h, car_h) + 0.3

    def _event_annotations(frame_time):
        # Show a label for each event whose time has been reached, stacked at
        # the top-left of the plot, so the moment is visible while scrubbing.
        anns = []
        for _j, (_label, _t) in enumerate(sorted(events.items(),
                                                  key=lambda kv: kv[1])):
            if frame_time + 1e-9 >= float(_t):
                anns.append(dict(
                    x=0.02, y=0.98 - _j * 0.12, xref="paper", yref="paper",
                    xanchor="left", yanchor="top", showarrow=False,
                    text="\u2605 %s (t=%.2f s)" % (_label, float(_t)),
                    font=dict(color="#444", size=12)))
        return anns

    frames = [
        go.Frame(data=_traces(i), name=f"{times[i]:.3f}",
                 layout=dict(annotations=_event_annotations(float(times[i]))))
        for i in idx
    ]
    frames += [
        go.Frame(data=_release_traces(release_brick_x[j]),
                 name=f"{release_times[j]:.3f}",
                 layout=dict(annotations=_event_annotations(
                     float(release_times[j]))))
        for j in range(n_release)
    ]

    fig = go.Figure(data=_traces(idx[0]), frames=frames)

    fig.add_shape(type="line", x0=x_min, x1=x_max, y0=ground_y, y1=ground_y,
                  line=dict(color="black", width=1))

    play_button = dict(
        label="Play", method="animate",
        args=[None, dict(frame=dict(duration=frame_ms, redraw=True),
                         fromcurrent=True,
                         transition=dict(duration=0))])
    pause_button = dict(
        label="Pause", method="animate",
        args=[[None], dict(frame=dict(duration=0, redraw=False),
                           mode="immediate",
                           transition=dict(duration=0))])

    slider = dict(
        steps=[dict(method="animate", label=f"{times[i]:.2f}",
                    args=[[f"{times[i]:.3f}"],
                          dict(mode="immediate",
                               frame=dict(duration=0, redraw=True),
                               transition=dict(duration=0))])
               for i in idx]
        + [dict(method="animate", label=f"{release_times[j]:.2f}",
                args=[[f"{release_times[j]:.3f}"],
                      dict(mode="immediate",
                           frame=dict(duration=0, redraw=True),
                           transition=dict(duration=0))])
           for j in range(n_release)],
        x=0.1, len=0.9, currentvalue=dict(prefix="time [s]: "))

    fig.update_layout(
        xaxis=dict(range=[x_min, x_max], zeroline=False, showgrid=False,
                   title="position [m]"),
        yaxis=dict(range=[ground_y - 0.05, y_max], zeroline=False,
                   showgrid=False, showticklabels=False,
                   scaleanchor="x", scaleratio=1),
        margin=dict(l=10, r=10, t=40, b=10),
        annotations=_event_annotations(float(times[idx[0]])),
        updatemenus=[dict(type="buttons", direction="left",
                          x=0.1, y=1.15, showactive=False,
                          buttons=[play_button, pause_button])],
        sliders=[slider],
    )
    return fig


class BrickSpringAnim():
    """Iterator class delivering images for animation
    one image pr. row in the dataframe"""

    def _create_base_im(self, h, w):
        _im = Image.fromarray(np.uint8(np.ones((self.h, self.w)) * 255))
        _draw_im = ImageDraw.Draw(_im)

        # Draw "ground"
        _draw_im.line([(0, h - 10), (w - 1, h - 10)], width=2, fill=0)
        _cx = 0
        while _cx < w:
            _draw_im.line([(_cx, h-1), (_cx + 10, h-10)], fill=0)
            _cx += 10
        return _im

    def __init__(self, df, font=None, h=100, w=600, cols=None):
        self.data = df

        if font is None:
            self.font = ImageFont.truetype(FONT_FILE, 20)
        else:
            self.font = font

        self.w = w
        self.h = h

        self.bw = 30
        self.bh = 30

        self.cw = 60
        self.ch = 35
        self.car_offset = 20

        _tot_xoffset = self.bw + self.cw + self.car_offset

        self.base_image = self._create_base_im(h, w + 2 * _tot_xoffset)
        self.pos2pix = (w - _tot_xoffset * 2)/6.0
        self.cols = df.columns if cols is None else cols

    def __len__(self):
        return self.data.shape[0]

    def _draw_brick(self, draw_im, i):
        # Draw brick
        _x_pos = int(self.data.iloc[i, 0] * self.pos2pix)
        _y_pos = self.h - self.bh - 13

        _c_rect = [(_x_pos, _y_pos),
                   (_x_pos + self.bw, _y_pos + self.bh)]
        draw_im.rectangle(_c_rect, outline=0, width=2)

    def _draw_car(self, draw_im, i):
        _x_inintial = self.bw + self.car_offset
        draw_im.line([(_x_inintial, self.h), (_x_inintial, self.h - 15)],
                     width=3, fill=0)
        _x_c = int(self.data.iloc[i, 2] * self.pos2pix) + \
            self.bw + self.car_offset
        _y_pos = self.h - self.ch - 15
        draw_im.line([(_x_c, self.h), (_x_c, self.h - 15)],
                     width=3, fill=0)

        _c_rect = [(_x_c, _y_pos),
                   (_x_c + self.cw, _y_pos + self.ch)]
        draw_im.rectangle(_c_rect, outline=0, width=2)
        # Draw wheels
        _wheel1 = [(_x_c + self.cw/4 - 6, _y_pos + self.ch - 7),
                   (_x_c + self.cw/4 + 6, _y_pos + self.ch + 5)]
        _wheel2 = [(_x_c + 3 * self.cw/4 - 6, _y_pos + self.ch - 7),
                   (_x_c + 3 * self.cw/4 + 6, _y_pos + self.ch + 5)]
        draw_im.ellipse(_wheel1, fill=100,
                        outline=0, width=1)
        draw_im.ellipse(_wheel2, fill=100,
                        outline=0, width=1)

    def _draw_spring(self, draw_im, i, elems=20):
        _c_ext = self.data.iloc[i, 4]
        _x_brick_end = int(self.data.iloc[i, 0] * self.pos2pix) + \
            self.bw
        _x_s = _x_brick_end + int(self.car_offset/2)
        _s_ext_pix = int(_c_ext * self.pos2pix)
        _x_se = _x_s + _s_ext_pix
        _y_upper = self.h - self.ch
        _y_lower = _y_upper + 15
        draw_im.line([(_x_s, _y_upper), (_x_s, _y_lower)], width=1, fill=0)
        draw_im.line([(_x_s + _s_ext_pix, _y_upper),
                      (_x_s + _s_ext_pix, _y_lower)], width=1, fill=0)
        draw_im.line([(_x_brick_end, _y_upper + 7),
                      (_x_s, _y_upper + 7)], width=1, fill=0)
        draw_im.line([(_x_se, _y_upper + 7),
                      (_x_se + self.car_offset/2, _y_upper + 7)], width=1,
                     fill=0)

        for _i in range(elems):
            _x_start = _x_s + int(_c_ext * (_i / elems) * self.pos2pix)
            _x_end = _x_s + int(_c_ext * ((_i + 1) / elems) * self.pos2pix)
            if _i % 2 == 0:
                _y_start, _y_end = _y_upper, _y_lower
            else:
                _y_start, _y_end = _y_lower, _y_upper
            draw_im.line([(_x_start, _y_start), (_x_end, _y_end)],
                         width=1, fill=0)

    def _draw_text(self, draw_im, i):
        t = self.data.index[i]
        draw_im.text((0, 0), "time: %0.02f [s]" % t,
                     fill=0, font=self.font)

        cols = _group_columns(self.cols)
        _y_loc = 20
        _x_loc = 0
        for c in cols:
            _c_unit = c[-1].split()[-1]
            for c_name in c[0]:
                _c_val = float(self.data.loc[t, c_name])
                _c_output = "%s: %0.2f %s" % (c_name, _c_val, _c_unit)
                _c_x_size = int(self.font.getlength(_c_output))
                draw_im.text((_x_loc, _y_loc), _c_output,
                             fill=0, font=self.font)
                _x_loc += _c_x_size + 10
                if _x_loc + _c_x_size > self.w:
                    _x_loc = 0
                    _y_loc += 20

    def _draw_frame(self, i):
        _im = self.base_image.copy()
        _draw_im = ImageDraw.Draw(_im)
        self._draw_brick(_draw_im, i)
        self._draw_spring(_draw_im, i)
        self._draw_car(_draw_im, i)
        self._draw_text(_draw_im, i)
        return _im

    def __getitem__(self, position):
        return self._draw_frame(position)
