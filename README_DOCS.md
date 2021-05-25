# Fly casting simulator in Python
The full package documentation is written in reStructuredText
for [Sphinx](https://www.sphinx-doc.org/en/master/).
In addition to Sphinx you'll also need to install the
Read The Docs theme
[sphinx-rtd-theme](https://sphinx-rtd-theme.readthedocs.io/en/stable/)
and the [Sphinx autoapi plugin](https://sphinx-autoapi.readthedocs.io/en/latest/index.html)
plugin is used to autgenerate API documentation form source code.

## Installing the packages
In order to build the documentation you'll need to install
the following packages:
```shell
pip install sphinx
pip install sphinx-rtd-theme
pip install sphinx-autoapi
```

## Build documentation
To build full documentation  (including detailed API docs)
move into the `doc/` folder and run:
```shell
$ sphinx-build -b html . _build
$ open _build/index.html
```

Or: 
```shell
$ make html
$ open html/index.html
```
