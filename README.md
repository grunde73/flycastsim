# flycastsim
App and library with functions for simulating flycasts.

The package is a work in progress, and it will (maybe) be
further developed when time and motivation permits.

The app is written in Python, and it is running in a browser
using the [https://streamlit.io/](https://streamlit.io/) framework.
The app is also publicly available at
[https://share.streamlit.io/grunde73/flycastsim/main](https://share.streamlit.io/grunde73/flycastsim/main)
(but the animations may not work 100% as intended due to
limited bandwidth).


## Quickstart
In order to run the app you'll need a working Python 3
installation/environment with pip for package installation.
Pyenv and/or Conda is recommended for separation of versions
and environments.

The following will usually work on (proper) UNIX based systems...

From the terminal do:
```shell
$ git clone git@github.com:grunde73/flycastsim.git
$ cd flycastsim
$ pip install -r requirements.txt
$ streamlit run streamlit_app.py 
```
Which will launch the app in your default browser. The instructions
above will also install the `flycast` package in your Python environment,
examples of its use is found in the `flysim_examples.ipyn` Jupyter
notebook.


## Disclaimer
```txt
"Essentially, all models are wrong, but some are useful."
George E. P. Box
```
Remember, models are just models. So be critical and aware
of the limitations and assumptions of all models, including
the ones found here :-D