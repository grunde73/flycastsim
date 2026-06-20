Develop / Contribute
=======================
Please read the following if you want to hack on or contribute to the
``flycastsim`` package.

The project is managed with `uv <https://docs.astral.sh/uv/>`_ and built with
the `hatchling <https://hatch.pypa.io/latest/>`_ build backend; all
configuration lives in ``pyproject.toml`` (there is no ``setup.py``).  After
cloning, ``uv sync --all-extras`` creates the ``.venv`` and installs the
package together with every optional dependency.


Package structure
---------------------
The project uses a ``src`` layout.  The package is split into two simulation
engines: ``sho`` (the simple 1-D *brick-spring-car* harmonic-oscillator model)
and ``fem`` (the continuum finite-element engine).  The main files and folders
are:

.. code-block:: text

    .
    ├── Open_Sans                 (folder - fonts for the streamlit app)
    ├── README.md                 (main readme file)
    ├── pyproject.toml            (project metadata, deps, build + tool config)
    ├── uv.lock                   (uv lock file - pinned dependency versions)
    ├── requirements.txt          (auto-generated with `uv export`, for plain pip)
    ├── MANIFEST.in               (extra files to ship in the sdist)
    ├── docs                      (folder - Sphinx documentation)
    ├── flysim_examples.ipynb     (Jupyter notebook with usage examples)
    ├── streamlit_app.py          (Streamlit simulator app)
    ├── src
    │   └── flycastsim            (folder - package source)
    │       ├── __init__.py       (public API re-exports)
    │       ├── sho               (simple 1-D brick-spring-car model)
    │       │   ├── model.py      (the forced-harmonic-oscillator simulation)
    │       │   ├── helpers.py    (plotly plotting + animation helpers)
    │       │   └── matlab        (original Matlab reference implementation)
    │       ├── fem               (continuum finite-element engine)
    │       ├── fem_helpers.py    (plotting/animation helpers for the fem casts)
    │       └── data              (bundled rod/line/leader component profiles)
    ├── tests                     (folder - pytest tests)
    │   ├── conftest.py           (fixtures for pytest)
    │   ├── pytest.ini            (pytest configuration)
    │   └── unit                  (folder - unit tests)
    └── .github/workflows         (CI: ci.yml runs tests, docs.yml deploys docs)


Test driven development
--------------------------
Please make sure any new functionality added to the package is tested
using `pytest`. All test code and data should be located in the
``./tests/`` folder in the package root folder.

Run the suite with::

    uv run pytest

The same tests run automatically in CI (``.github/workflows/ci.yml``) on every
push and pull request against ``main``.

For more information on using and running ``pytest`` see `pytest documentation <https://docs.pytest.org/en/latest/index.html>`_
or a random `tutorial <https://semaphoreci.com/community/tutorials/testing-python-applications-with-pytest>`_
or this `tutorial <https://realpython.com/pytest-python-testing/>`_ .


Documentation
---------------
The documentation is built using `Sphinx <https://www.sphinx-doc.org/en/master/index.html>`_
and `reStructuredText <https://docutils.sourceforge.io/rst.html>`_, including
automatically generated API documentation from source doc-strings (via
`sphinx-autoapi <https://sphinx-autoapi.readthedocs.io/>`_).

Build the docs locally with the ``docs`` optional dependencies::

    uv run --extra docs --directory docs make html

The result is written to ``docs/build/html`` (this folder is git-ignored and
should not be committed).

Documentation is published automatically to `GitHub Pages
<https://grunde73.github.io/flycastsim>`_ by the ``.github/workflows/docs.yml``
workflow on every push to ``main``: it rebuilds the Sphinx site and deploys it
with ``actions/deploy-pages``.  There is no need to build or commit the HTML by
hand.

For more on the required packages see the project ``README.md``.
