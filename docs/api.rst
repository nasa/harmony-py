.. _api:

API Documentation
=================

.. module:: harmony

Here we cover the package and its modules, focusing first on the classes normally imported when working with Harmony.

Top-level Package API
---------------------

The classes in the ``harmony`` package that are used for crafting a request, submitting it to Harmony, and getting the results.

.. autoclass:: harmony.Request

.. autoclass:: harmony.Client

When creating a request, the ``BBox`` and ``Collection`` classes are used to create a valid request.

.. autoclass:: harmony.BBox

.. autoclass:: harmony.Collection


Authenticating with Earthdata Login
-----------------------------------

HarmonyPy requires that you have a valid `Earthdata Login account <https://urs.earthdata.nasa.gov/home)>`_. There are three ways to use your EDL account with HarmonyPy:

1. Provide your credentials when creating a HarmonyPy ``Client`` ::

    harmony_client = Client(auth=('captainmarvel', 'marve10u5'))

2. Set your credentials using environment variables ::

    $ export EDL_USERNAME='captainmarvel'
    $ export EDL_PASSWORD='marve10u5'

3. Uset a ``.netrc`` file:

    Create a ``.netrc`` file in your home directory, using the example below:

    .. code-block:: shell

    machine urs.earthdata.nasa.gov
    login captainmarvel
    password marve10u5

Exceptions
----------

Exceptions that may be raised when authenticating with Earthdata Login.

.. autoexception:: harmony.auth.MalformedCredentials

.. autoexception:: harmony.auth.BadAuthentication

Developer Documentation
-----------------------

Here we show the full API documentation. This will most often be used when developing on the HarmonyPy package, and will not likely be needed if you are using HarmonyPy to make requests. 

Submodules
----------

harmony.auth module
-------------------

.. automodule:: harmony.auth
   :members:
   :undoc-members:
   :show-inheritance:

harmony.config module
---------------------

.. automodule:: harmony.config
   :members:
   :undoc-members:
   :show-inheritance:

harmony.harmony module
----------------------

.. automodule:: harmony.harmony
   :members:
   :undoc-members:
   :show-inheritance:

Module contents
---------------

.. automodule:: harmony
   :members:
   :undoc-members:
   :show-inheritance:
