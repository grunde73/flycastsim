Develop / Contribute
=======================
Please read the following if you want to hack on or contribute to the `flycast`
package.


Package structure
---------------------
The package structure follows "the typical" `setuptool` structure, with the following
(main) files and folders:



.. code-block:: txt

    .
    ├── Open_Sans             (folder - fonts for streamlit app)
    ├── README.md             (main readme file)
    ├── docs                  (folder - documentation)
    ├── flysim_examples.ipynb (Jupyter notebook with usage examples)
    ├── requirements.txt      (main package requirements)
    ├── setup.py              (setuptools package config)
    ├── src
    │   ├── flycast           (folder - package source)
    ├── streamlit_app.py      (Streamlit simulator app)
    ├── tests                 (folder - pytest test folder)
    │   ├── conftest.py       (fixtures for pytest)
    │   └── unit              (folder - unit tests)


 
Test driven development
--------------------------
Please make sure any new functionality added to the package is tested
using `pytest`. All test code and data should be located in the
`./tests/` folder in the package root folder.

For more information on using and running ``pytest`` see `pytest documentation <https://docs.pytest.org/en/latest/index.html>`_
or a random `tutorial <https://semaphoreci.com/community/tutorials/testing-python-applications-with-pytest>`_
or this `tutorial <https://realpython.com/pytest-python-testing/>`_ .


Documentation
---------------
The documentation is build using `Sphinx <https://www.sphinx-doc.org/en/master/index.html>`_
and `reStructuredText <https://docutils.sourceforge.io/rst.html>`_, including automatically generated
API documentation from source doc-strings.
