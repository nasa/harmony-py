# harmony-py

`harmony-py` is a Python library for integrating with NASA's [Harmony](https://harmony.earthdata.nasa.gov/).

`harmony-py` is an alternative to [Harmony's RESTful API](https://harmony.earthdata.nasa.gov/docs/api/), handles NASA [Earthdata Login (EDL)](https://urs.earthdata.nasa.gov/home) authentication and optionally integrates with the [CMR Python Wrapper](https://github.com/nasa/eo-metadata-tools) by accepting collection results as a request parameter. It's convenient for scientists who wish to use Harmony from Jupyter notebooks as well as machine-to-machine communication with larger Python applications.

`harmony-py` is a work-in-progress, is not feature complete, and should only be used if you would like to test `harmony-py` functionality.

![Python package](https://github.com/nasa/harmony-py/workflows/Python%20package/badge.svg)

---

## Installing

The library is available from [PyPI](#TODO) and can be installed with pip:

> pip install -U harmony-py

## Running the Example Jupyter Notebooks

Jupyter notebooks in the `examples` subdirectory show how to use the Harmony Py library. Start up the Jupyter Lab notebook server and run these examples: 

The Jupyter Lab server will start and [open in your browser](http://localhost:8888/lab). Double-click on a notebook in the file-browser sidebar and run the notebook. Note that some notebooks may have cells which prompt for your EDL username and password. Be sure to use your UAT credentials since all of the example notebooks use the Harmony UAT environment.

> make examples

## Developing

Before installing dependencies, either create and activate a Python virtual environment, or if you have pyenv and pyenv-virtualenv installed, use the `virtualenv` make target to create and activate one for you (`harmony-py`):

> make virtualenv

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

Run unit tests and test coverage. This will display terminal output and generate an HTML coverage report in the `htmlcov` directory.

> make test

For development, you may want to run the unit tests continuously as you update tests and the code-under-test:

> make test-watch


### Generating Request Parameters

The `harmony.Request` constructor can accept parameters that are defined in the [Harmony OGC API schema](). If this schema has been changed and the `Request` constructor needs to be updated, you may run the generator utility. This tool reads the Harmony schema and generates a partial constructor signature with docstrings:

> python internal/genparams.py ${HARMONY_DIR}/app/schemas/ogc-api-coverages/1.0.0/ogc-api-coverages-v1.0.0.yml

Either set HARMONY_DIR or replace it with your Harmony project directory path. You may then write standard output to a file and then use it to update the `harmony.Request` constructor and code.

## CI

Harmony-py uses [GitHub
Actions](https://github.com/nasa/harmony-py/actions) to run the Linter
& Unit Tests. The test coverage output is saved as a build artifact.
