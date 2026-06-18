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
The project is managed with [uv](https://docs.astral.sh/uv/). Install uv
(see the [uv installation docs](https://docs.astral.sh/uv/getting-started/installation/)),
then from the terminal do:
```shell
$ git clone git@github.com:grunde73/flycastsim.git
$ cd flycastsim
$ uv sync --extra app
$ uv run streamlit run streamlit_app.py
```
This creates an isolated virtual environment (`.venv`), installs the
`flycastsim` package together with the app dependencies, and launches the
app in your default browser. uv automatically provisions a compatible
Python interpreter (>= 3.12) for you.

Examples of using the `flycastsim` package are found in the
`flysim_examples.ipynb` Jupyter notebook.

A `requirements.txt` (auto-generated with `uv export`) is also provided for
environments that use plain `pip`, such as Streamlit Community Cloud:
```shell
$ pip install -r requirements.txt
$ streamlit run streamlit_app.py
```


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
$ uv run --extra docs --directory docs make html
$ open docs/build/html/index.html
```

The docs are also available online here:
[https://grunde73.github.io/flycastsim](https://grunde73.github.io/flycastsim)


## Disclaimer
> "Essentially, all models are wrong, but some are useful."
> George E. P. Box

Remember, models are just models. So be critical and aware
of the limitations and assumptions of all models, including
the ones found here :-D