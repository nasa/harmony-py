# harmony-py

`harmony-py` is a Python library for integrating with NASA's [Harmony](https://harmony.earthdata.nasa.gov/).

`harmony-py` is an alternative to [Harmony's RESTful API](https://harmony.earthdata.nasa.gov/docs/api/), handles NASA [Earthdata Login (EDL)](https://urs.earthdata.nasa.gov/home) authentication and optionally integrates with the [CMR Python Wrapper](https://github.com/nasa/eo-metadata-tools) by accepting collection results as a request parameter. It's convenient for scientists who wish to use Harmony from Jupyter notebooks as well as machine-to-machine communication with larger Python applications.

`harmony-py` is a work-in-progress, is not feature complete, and should only be used if you would like to test `harmony-py` functionality.

![Python package](https://github.com/nasa/harmony-py/workflows/Python%20package/badge.svg)

---

## Installing

The library is available from Pypi and can be installed with pip:

> pip install -U harmony-py


## Developing

Install dependencies:

> make install

Optionally register your local copy with pip:

> pip install -e ./path/to/harmony_py


### Generating Documentation

Documentation is formatted in reStructuredText (.rst) and generated with `sphinx`. To build the documentation:

> make docs

You can then view the documentation in a web browser under ./docs/_build/html/index.html


### Running the Linter & Unit Tests

Run the linter on the project source:

> make lint

Tests use `unittest` and can run with nose and generate test coverage
which can be seen in HTML form in the `htmlcov` subdirectory.

> make test


## CI

Harmony-py uses [GitHub
Actions](https://github.com/nasa/harmony-py/actions) to run the Linter
& Unit Tests. The test coverage output is saved as a build artifact.
