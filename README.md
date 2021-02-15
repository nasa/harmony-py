TESTING

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

Install requirements:

> pip install -r requirements/core.txt -r requirements/dev.txt

Optionally register your local copy with pip:

> pip install -e ./path/to/harmony_py


### Generating Documentation

Documentation is formatted in reStructuredText (.rst) and generated with `sphinx`. To build the documentation, go to ./docs and issue the following command:

> make html

You can then view the documentation in a web browser under ./docs/_build/html/index.html


### Running Tests

Tests use `unittest` and can run with nose and coverage:

> nosetests --with-coverage --cover-html --cover-branches --cover-package=harmony_py --cover-erase --nocapture --nologcapture


### Running the Linter

Harmony-py uses `flake8`. To run manually:

> flake8 ./harmony_py
