"""
Helper functions to deal with data from brick-spring-car
modelling.
"""
import numpy as np
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import os

from PIL import Image, ImageDraw, ImageFont


_c_dir = os.path.join(os.path.dirname(os.path.dirname(__file__))) # ,"..", 'Open_Sans')
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

def plot_brick_spring(df, plot_cols):
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
    return fig


class BrickSpringAnim():
    """Iterator class delivering images for animation
    one image pr. row in the dataframe"""

    def _create_base_im(self, h, w):
        _im = Image.fromarray(np.uint8(np.ones((self.h, self.w, 3)) * 255))
        _draw_im = ImageDraw.Draw(_im)

        # Draw "ground"
        _draw_im.line([(0, h - 10), (w - 1, h - 10)], width=2, fill=0)
        _cx = 0
        while _cx < w:
            _draw_im.line([(_cx, h-1), (_cx + 10, h-10)], fill=0)
            _cx += 10
        return _im


    def __init__(self, df, font=None, h=150, w=1000, cols=None):
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
        self.pos2pix = (w - _tot_xoffset * 2)/6.0 #  self.data.iloc[-1,0]
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
                     width=3, fill=(255, 0, 0))
        _x_c = int(self.data.iloc[i, 2] * self.pos2pix) + \
               self.bw + self.car_offset
        _y_pos = self.h - self.ch - 15
        draw_im.line([(_x_c, self.h), (_x_c, self.h - 15)],
                     width=3, fill=(255,0,0))

        _c_rect = [(_x_c, _y_pos),
                   (_x_c + self.cw, _y_pos + self.ch)]
        draw_im.rectangle(_c_rect, outline=0, width=2)
        # Draw wheels
        _wheel1 = [(_x_c + self.cw/4 - 6, _y_pos + self.ch - 7),
                   (_x_c + self.cw/4 + 6, _y_pos + self.ch + 5)]
        _wheel2 = [(_x_c + 3 * self.cw/4 - 6, _y_pos + self.ch - 7),
                   (_x_c + 3 * self.cw/4 + 6, _y_pos + self.ch + 5)]
        draw_im.ellipse(_wheel1, fill=(100, 100, 100),
                        outline=0, width=1)
        draw_im.ellipse(_wheel2, fill=(100, 100, 100),
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
                      (_x_se + self.car_offset/2, _y_upper + 7)], width=1, fill=0)

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
        _y_loc = 30
        _x_loc = 0
        for c in cols:
            _c_unit = c[-1].split()[-1]
            for c_name in c[0]:
                _c_val = float(self.data.loc[t, c_name])
                _c_output = "%s: %0.2f %s" % (c_name, _c_val, _c_unit)
                _c_x_size = self.font.getsize(_c_output)[0]
                draw_im.text((_x_loc, _y_loc), _c_output,
                             fill=0, font=self.font)
                _x_loc += _c_x_size + 25
                if _x_loc + _c_x_size > self.w:
                    _x_loc = 0
                    _y_loc += 25


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