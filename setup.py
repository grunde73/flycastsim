# -*- coding: utf-8 -*-
"""A setuptools based module for the Basefarm blitz python wrapper.
"""

from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README.md file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

def read(rel_path):
    here = path.abspath(path.dirname(__file__))
    with open(path.join(here, rel_path), 'r') as fp:
        return fp.read()

def get_version(rel_path):
    for line in read(rel_path).splitlines():
        if line.startswith('__version__'):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    else:
        raise RuntimeError("Unable to find version string.")

setup(
    name='flycast',

    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    # Ser the version number in the __init__.py function.
    version=get_version("src/flycast/__init__.py"),
    description="Python package with functionality for simulations of flycasting",
    long_description=long_description,

    # The project's main homepage.
    url='https://github.com/grunde73/flycastsim',

    # Author details
    author='Grunde Løvoll',
    author_email='grunde@fiskekroken.org',

    # Choose your license
    license='BSD 2-Clause License',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers :: Physics simulations',
        'Topic :: Simulations :: Simulatins flycasting',

        # Pick your license as you wish (should match "license" above)
        'License :: BSD 2-Clause License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
    ],

    keywords='simulations',
    packages=find_packages(where='src', exclude=['contrib', 'doc', 'tests']),
    package_dir={'': 'src'},
    install_requires=['numpy', 'scipy', 'pandas'],
    # test_suite='tests', # dropping this because not testing with setuptools
    scripts=[],
    include_package_data=True,
)
