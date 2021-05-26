# flycastsim
A web-app and library with functions for simulating flycasts.

The package is a work in progress, and it will (maybe) be
further developed when time and motivation permits.

The app is written in Python, and it is running in a browser
using the [https://streamlit.io/](https://streamlit.io/) framework.
The app is also publicly available at
[https://share.streamlit.io/grunde73/flycastsim/main](https://share.streamlit.io/grunde73/flycastsim/main)
(but the animations may not work 100% as intended due to
limited bandwidth).

Up-to date documentation is found at:
[https://grunde73.github.io/flycastsim](https://grunde73.github.io/flycastsim)


## Quickstart
In order to run the app you'll need a working Python 3
installation/environment with pip for package installation.
Using [pyenv](https://github.com/pyenv/pyenv)
and/or Conda is highly recommended for separation of Python
versions and environments.

The following will usually work on (proper) UNIX based systems...

From the terminal do:
```shell
$ git clone git@github.com:grunde73/flycastsim.git
$ cd flycastsim
$ pip install -r requirements.txt
$ streamlit run streamlit_app.py 
```
Which will launch the app in your default browser. The instructions
above will also install the `flycastsim` package in your Python environment,
examples of its use is found in the `flysim_examples.ipynb` Jupyter
notebook.


## Documentation
The full package documentation is found in the [docs](./docs/)
folder, and it is written in reStructuredText
for [Sphinx](https://www.sphinx-doc.org/en/master/).

In addition to Sphinx you'll also need to install the
Read The Docs theme
[sphinx-rtd-theme](https://sphinx-rtd-theme.readthedocs.io/en/stable/)
and the [Sphinx autoapi plugin](https://sphinx-autoapi.readthedocs.io/en/latest/index.html)
plugin is used to autogenerate API documentation form source code.

The following commands will install the needed packages,
build and open the documentation.
```shell
$ cd docs
$ pip install sphinx
$ pip install sphinx-rtd-theme
$ pip install sphinx-autoapi
$ make html
$ open build/html/index.html
```

The docs are also available online here:
[https://grunde73.github.io/flycastsim](https://grunde73.github.io/flycastsim)


## Disclaimer
> "Essentially, all models are wrong, but some are useful."
> George E. P. Box

Remember, models are just models. So be critical and aware
of the limitations and assumptions of all models, including
the ones found here :-D