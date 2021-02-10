# harmony-py

`harmony-py` is a Python library for integrating with NASA's [Harmony](https://harmony.earthdata.nasa.gov/).

`harmony-py` is an alternative to [Harmony's RESTful API](https://harmony.earthdata.nasa.gov/docs/api/), handles NASA [Earthdata Login (EDL)](https://urs.earthdata.nasa.gov/home) authentication and optionally integrates with the [CMR Python Wrapper](https://github.com/nasa/eo-metadata-tools) by accepting collection results as a request parameter. It's convenient for scientists who wish to use Harmony from Jupyter notebooks as well as machine-to-machine communication for larger Python applications.

`harmony-py` is a work-in-progress, is not feature complete, and should only be used if you would like to test `harmony-py` functionality.