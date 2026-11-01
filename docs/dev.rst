Develop / Contribute
=======================
Please read the following if you want to hack on or contribute to the
``flycastsim`` package.

The project is managed with `uv <https://docs.astral.sh/uv/>`_ and built with
the `hatchling <https://hatch.pypa.io/latest/>`_ build backend; all
configuration lives in ``pyproject.toml`` (there is no ``setup.py``).  After
cloning, ``uv sync --all-extras`` creates the ``.venv`` and installs the
package together with every optional dependency (the ``dev`` and ``app``
dependency groups are installed by default).  Run the app locally with
``uv run streamlit run streamlit_app.py``.


Package structure
---------------------
The project uses a ``src`` layout.  The package has two simulation engines,
``sho`` (the simple 1-D *brick-spring-car* harmonic-oscillator model) and
``fem`` (the continuum finite-element engine), and ``rod`` (rod parameters:
swingweight and the stiffness/mass profile fit).  The main files and folders
are:

.. code-block:: text

    .
    ├── Open_Sans                 (folder - fonts for the streamlit app)
    ├── README.md                 (main readme file)
    ├── pyproject.toml            (project metadata, deps, build + tool config)
    ├── uv.lock                   (uv lock file - pinned dependency versions)
    ├── requirements.txt          (auto-generated with `uv export`, for plain pip)
    ├── .pre-commit-config.yaml   (the pre-commit hook's checks)
    ├── openspec                  (folder - specs and change proposals)
    ├── scripts                   (dependency audit, requirements.txt check)
    ├── docs                      (folder - Sphinx documentation)
    ├── flysim_examples.ipynb     (Jupyter notebook with usage examples)
    ├── examples                  (scripts, e.g. rod_profile_fit.py)
    ├── assets                    (measurement data sets: <ROD>/rod.yaml,
    │                              bend-test frames, frequency tests, fits;
    │                              not packaged)
    ├── streamlit_app.py          (Streamlit simulator app)
    ├── rod_profile_pages.py      (app views: Stiffness profiles, Upload & fit)
    ├── src
    │   └── flycastsim            (folder - package source)
    │       ├── __init__.py       (public API re-exports)
    │       ├── sho               (simple 1-D brick-spring-car model)
    │       │   ├── model.py      (the forced-harmonic-oscillator simulation)
    │       │   ├── helpers.py    (plotly plotting + animation helpers)
    │       │   └── matlab        (original Matlab reference implementation)
    │       ├── fem               (continuum finite-element engine)
    │       ├── fem_helpers.py    (plotting/animation helpers for the fem casts)
    │       ├── rod               (rod parameters: swingweight, elastica,
    │       │                      vibration, imaging, profile fit, fitted
    │       │                      rods, rod.yaml loader, archives)
    │       └── data              (bundled rod/line/leader component profiles,
    │                              fitted rods, example and measured rods)
    ├── tests                     (folder - pytest tests)
    │   ├── conftest.py           (fixtures for pytest)
    │   ├── pytest.ini            (pytest configuration)
    │   └── unit                  (folder - unit tests)
    └── .github/workflows         (ci.yml runs checks and tests, security.yml
                                   audits dependencies, docs.yml deploys docs)


Test driven development
--------------------------
Please make sure any new functionality added to the package is tested
using `pytest`. All test code and data should be located in the
``./tests/`` folder in the package root folder.

Run the suite with::

    uv run pytest

The same tests run automatically in CI (``.github/workflows/ci.yml``) on every
push and pull request against ``main``, together with Ruff, the import
contracts, the ``requirements.txt`` check and spec validation.

For more information on using and running ``pytest`` see `pytest documentation <https://docs.pytest.org/en/latest/index.html>`_
or a random `tutorial <https://semaphoreci.com/community/tutorials/testing-python-applications-with-pytest>`_
or this `tutorial <https://realpython.com/pytest-python-testing/>`_ .


Pre-commit checks
--------------------
Install the hook once per checkout::

    uv run pre-commit install

It needs the ``openspec`` command, which requires Node 22.12 or newer::

    npm install -g @fission-ai/openspec

Each commit then runs the checks that apply to the staged files:

.. list-table::
   :header-rows: 1

   * - Check
     - Runs when
   * - ``ruff check``, including the ``S`` security rules
     - Python files change
   * - ``lint-imports``: ``flycastsim.fem`` stays plotting-free
     - ``src/`` or ``pyproject.toml`` changes
   * - The app imports only the public API
     - ``streamlit_app.py`` or ``rod_profile_pages.py`` changes
   * - ``openspec validate --all --strict``
     - ``openspec/`` changes
   * - ``scripts/check_requirements.sh``: ``requirements.txt`` matches
       ``uv.lock``
     - ``pyproject.toml``, ``uv.lock`` or ``requirements.txt`` changes
   * - ``scripts/check_audit.sh``: ``uv audit`` finds no known vulnerabilities
     - ``pyproject.toml`` or ``uv.lock`` changes
   * - gitleaks: no secrets in the staged changes
     - Every commit

Please don't bypass the hook with ``--no-verify``.  To run it on all tracked
files::

    uv run pre-commit run --all-files

The audit needs network access.  Because new advisories appear without any change
in this repository, ``.github/workflows/security.yml`` also runs it every week.
The full test suite takes minutes, so it runs in CI rather than in the hook.


Specs and proposals (OpenSpec)
---------------------------------
Behaviour and constraints are specified with `OpenSpec
<https://github.com/Fission-AI/OpenSpec>`_ under ``openspec/``:

* ``openspec/specs/`` holds the current specs.  ``architecture/spec.md`` lists the
  project-wide constraints, each naming the check that enforces it or marked as
  relying on review.
* ``openspec/changes/`` holds proposed changes, and ``changes/archive/`` the
  completed ones.
* ``openspec/config.yaml`` gives agents the project context and the rules for
  writing each artifact.

A change needs a proposal if it alters numerics in a way that can change converged
solutions, the public API, a data format, or a fit method, or if it adds a
capability or changes an architecture requirement.  Other changes skip proposals,
such as measurement data, new fitted rods in an existing format, bug fixes that
restore specified behaviour, refactors and documentation.  If a change turns out
to need a spec change, write the proposal first.  An area without a spec gets one
when it first needs a proposal.

Claude Code and GitHub Copilot both have the workflow commands (``/opsx-propose``
and so on in Copilot):

#. ``/opsx:propose`` writes the proposal, spec changes, design and tasks.
#. ``/opsx:apply`` implements the tasks.
#. ``/opsx:archive`` merges the spec changes into ``openspec/specs/`` and moves
   the change to the archive.

Each spec scenario names the test or check that proves it, or says it relies on
review.  To validate everything by hand::

    openspec validate --all --strict

OpenSpec collects anonymous usage statistics by default.  To opt out, run
``openspec config set telemetry.enabled false`` or set ``OPENSPEC_TELEMETRY=0``.


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
