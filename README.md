# harmony-py

`harmony-py` is a Python library for integrating with NASA's [Harmony](https://harmony.earthdata.nasa.gov/).

`harmony-py` is an alternative to [Harmony's RESTful API](https://harmony.earthdata.nasa.gov/docs/api/), handles NASA [Earthdata Login (EDL)](https://urs.earthdata.nasa.gov/home) authentication and optionally integrates with the [CMR Python Wrapper](https://github.com/nasa/eo-metadata-tools) by accepting collection results as a request parameter. It's convenient for scientists who wish to use Harmony from Jupyter notebooks as well as machine-to-machine communication with larger Python applications.

`harmony-py` is a work-in-progress, is not feature complete, and should only be used if you would like to test `harmony-py` functionality.

![Python package](https://github.com/nasa/harmony-py/workflows/Python%20package/badge.svg)

---
# Using Harmony Py

## Prerequisites

* Python 3.7+


## Installing

The library is available from [PyPI](https://pypi.org/project/harmony-py/) and can be installed with pip:

        $ pip install -U harmony-py

This will install harmony-py and its dependencies into your current Python environment. It's recommended that you install harmony-py into a virtualenv along with any other dependencies you may have.


# Running Examples & Developing on Harmony Py

## Prerequisites

* Python 3.7+
* (optional,recommended) [pyenv](https://github.com/pyenv/pyenv) and [pyenv-virtualenv](https://github.com/pyenv/pyenv-virtualenv)


## Installing Development & Example Dependencies

First, it's recommended that you create a Python virtualenv so that Harmony Py and its dependencies are isolated in their own environment. To do so, you can either [create and activate a Python virtual environment with venv](https://docs.python.org/3/tutorial/venv.html), or--if you have pyenv and pyenv-virtualenv installed--use pyenv to create and activate one for you (`harmony-py`). There are `make` targets for both of these options--choose one.

1a. Create a virtualenv with venv:

        $ make venv-setup
        $ source .venv/bin/activate

To deactivate it:

        $ source deactivate

1b. Use pyenv & pyenv-virtualenv. This will install Python 3.9 & create a virtualenv using that version of Python. Important: if this is your first time using pyenv to install Python, be sure that you have the [Python build requirements installed](https://github.com/pyenv/pyenv/wiki#suggested-build-environment) first.

        $ make pyenv-setup

If you've setup pyenv with your shell properly, it should automatically activate the environment. You can check if it's activated by:

        $ pyenv version

It should show `harmony-py`. Pyenv does auto-activation by creating a `.python-version` file in the project directory. Most shells can be setup to automatically activate & deactivate virtual environments when cd'ing into & out of directories by using the value found in `.python-version`. This is convenient since it ensures that the correct virtualenv has been activated (and deactivated) when starting work on a project. See the pyenv docs for more details. If you need to manually activate & deactivate:

        $ pyenv activate harmony-py
        $ pyenv deactivate

2. Install dependencies:

        $ make install

3. Optionally register your local copy with pip:

        $ pip install -e ./path/to/harmony_py


## Running the Example Jupyter Notebooks

Jupyter notebooks in the `examples` subdirectory show how to use the Harmony Py library. Start up the Jupyter Lab notebook server and run these examples: 

The Jupyter Lab server will start and [open in your browser](http://localhost:8888/lab). Double-click on a notebook in the file-browser sidebar and run the notebook. Note that some notebooks may have cells which prompt for your EDL username and password. Be sure to use your UAT credentials since all of the example notebooks use the Harmony UAT environment.

        $ make examples


## Developing

### Generating Documentation

Documentation is formatted in reStructuredText (.rst) and generated with `sphinx`. To build the documentation:

        $ make docs

You can then view the documentation in a web browser under ./docs/_build/html/index.html


### Running the Linter & Unit Tests

Run the linter on the project source:

        $ make lint

Run unit tests and test coverage. This will display terminal output and generate an HTML coverage report in the `htmlcov` directory.

        $ make test

For development, you may want to run the unit tests continuously as you update tests and the code-under-test:

        $ make test-watch


### Generating Request Parameters

The `harmony.Request` constructor can accept parameters that are defined in the [Harmony OGC API schema](). If this schema has been changed and the `Request` constructor needs to be updated, you may run the generator utility. This tool reads the Harmony schema and generates a partial constructor signature with docstrings:

        $ python internal/genparams.py ${HARMONY_DIR}/app/schemas/ogc-api-coverages/1.0.0/ogc-api-coverages-v1.0.0.yml

Either set `HARMONY_DIR` or replace it with your Harmony project directory path. You may then write standard output to a file and then use it to update the `harmony.Request` constructor and code.

## CI

Harmony-py uses [GitHub
Actions](https://github.com/nasa/harmony-py/actions) to run the Linter
& Unit Tests. The test coverage output is saved as a build artifact.

## Building and Releasing

If a new version of Harmony-Py will be released then the `master` branch should be tagged with an updated version:

        $ git checkout master
        $ git tag -a v1.2.3    # where v1.2.3 is the next version number

In order to generate new package and wheel files, do the following:

        $ make build

`make` reads the current version number based on git tag, populates the version in `harmony/__init__.py`, and `setup.py` reads the version number from `harmony/__init__.py` for packaging purposes.

This leaves us with a modifed __init\__.py which must be committed and pushed to `master`.

        $ git add harmony/__init__.py
        $ git commit -m "Version bump to v1.2.3"
        $ git tag -f
        $ git push

Then, provided API tokens are in order, the following runs the build target and publishes to PyPI:

        $ make publish
