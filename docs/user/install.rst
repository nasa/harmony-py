.. _install:

Installing HarmonyPy
====================

Before we can start using HarmonyPy, we need to install it.


Install from PyPI using pip
---------------------------

To install HarmonyPy, use pip to pull the latest version from `PyPI <https://pypi.org/>`_. Note that you may not want to install this in your Python system directory. See below for options.

To install using pip ::

    $ pip install harmony-py

To install into your user directory ::

    $ pip install --user harmony-py

Other options include making a virtual environment using ``venv``, or creating a ``conda`` environment and installing it there. We'll show how to create a virtualenv here, but see the conda documentation for creating a conda env and installing it there.

Using venv ::

    $ python -m venv env
    $ source env/bin/activate
    $ pip install harmony-py

This will create a directory named ``env`` in the current working directory, and by activating it, pip will install ``harmony-py`` in the ``env`` directory tree, isolating it from other projects. See the `Python Packaging site <https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/#creating-a-virtual-environment>`_ for more details about creating and using Python virtual environments.

Getting the Code
----------------

HarmonyPy is actively developed on GitHub and the code is
`publicly available <https://github.com/nasa/harmony-py>`.

Clone the repository ::

    $ git clone https://github.com/nasa/harmony-py.git
