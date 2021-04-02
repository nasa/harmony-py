HarmonyPy: NASA Harmony Python Client
=====================================

Harmony-Py provides a Python alternative to directly using `Harmony's RESTful API <https://harmony.earthdata.nasa.gov/docs/api/>`_. It handles NASA `Earthdata Login (EDL) <https://urs.earthdata.nasa.gov/home>`_ authentication and optionally integrates with the `CMR Python Wrapper <https://github.com/nasa/eo-metadata-tools>`_ by accepting collection results as a request parameter. It's convenient for scientists who wish to use Harmony from Jupyter notebooks as well as machine-to-machine communication with larger Python applications.

Harmony-Py is a work-in-progress, is not feature complete, and should only be used if you would like to test its functionality. We welcome feedback on Harmony-Py via `GitHub Issues <https://github.com/nasa/harmony-py/issues>`_.

.. image:: https://github.com/nasa/harmony-py/workflows/Python%20package/badge.svg
    :target: https://github.com/nasa/harmony-py

.. image:: https://readthedocs.org/projects/harmony-py/badge/?version=latest)](https://harmony-py.readthedocs.io/en/latest/?badge=latest
    :target: https://github.com/nasa/harmony-py

-------------------

**Harmony In Action** ::

    >>> harmony_client = Client(auth=('captainmarvel', 'marve10u5'))

    >>> request = Request(
            collection=Collection(id='C1234088182-EEDTEST'),
            spatial=BBox(-140, 20, -50, 60),
            crs='EPSG:3995',
            format='image/tiff',
            height=512,
            width=512
        )

    >>> job_id = harmony_client.submit(request)

    >>> harmony_client.download_all(job_id)

-------------------

User Guide
----------

How to install HarmonyPy, and a quick tutorial to get you started with your own Harmony requests.

.. toctree::
   :maxdepth: 2

   user/install
   user/tutorial

API Documentation
-----------------

Specific documentation on the HarmonyPy package, its modules, and their functions, classes, and methods.

.. toctree::
   :maxdepth: 2

   api

Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
