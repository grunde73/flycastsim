import streamlit as st
import cufflinks as cf

from flycast import brick_spring_simple

st.title("Flycast simulator")
st.write("""
This is the start of an open and free flycasting simulator.

The app is a work in process and it will be developed in an ad-hock
fashion when I have the time.
The project will also be used to learn and get practical experience
using the Streamlit framework.
""")

# Add widget for brick-spring-car model
# import pandas as pd

st.write("""
## Understanding spring -- sling
Introduction to the *brick-spring-car* model, and
why it is a good model for understanding the relation
and interplay of spring and leverage in
flycasting.
""")
k = 1.0
m = 0.01
d0 = 0
start_cond = [0, 0]  # [x(t0), v(t0)]
ts = [1.0, 0.3, 0.45]  # [sim_tmax, t_break, t_stop]
vct = [0, 18, 0]  # [v_car(t0), v_car_max, v_car_end]
res = brick_spring_simple(k, m, d0, start_cond, ts, vct)
# st.write(res)
st.write("Speed evolution of brick and car")
speed_fig = res.loc[:, ['v', 'car_speed']].iplot(asFigure=True,
                                                 xTitle=r"$Time\ \ [s]$",
                                                 yTitle=r"$Speed\ \ [m/s]$")
st.plotly_chart(speed_fig)

st.write("Energy in brick and in spring as function of time")
energy_fig = res.loc[:, ['sp_e', 'brick_e']].iplot(asFigure=True,
                                  xTitle=r"$Time\ \ [s]$",
                                  yTitle=r"$Energy\ \ [J]$")
st.plotly_chart(energy_fig)

# st.write("Force and power from car on brick")

### FIXME: make multiple plots thingy

# force_fig = res.loc[:, ['sp_e', 'brick_e']].iplot(asFigure=True,
#                                   xTitle=r"$Time\ \ [s]$",
#                                   yTitle=r"$Energy\ \ [J]$")
# force_fig = cf.Figure()
# force_fig.set_subplots(rows=2, cols=1, shared_xaxes=True)
# force_fig.add_trace(res.loc[:, ['force',]].figure(yTitle=r"$Force\ \ [N]$"))
# force_fig.add_trace(res.loc[:,['car_p',]].figure(yTitle=r"$Power\ \ [W]$",
#                                                  xTitle=r"$Time\ \ [s]$"))
# st.plotly_chart(force_fig)