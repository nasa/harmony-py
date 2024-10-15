import sys
import os
sys.path.append('..')

import datetime as dt
from getpass import getpass
from glob import glob
from time import sleep

import ipyplot
from ipywidgets import IntSlider, Password, Text
from IPython.display import display, JSON
import rasterio
from rasterio.plot import show
import requests

def install_project_and_dependencies(project_root, libs=None):
    """
    Change to the project root, install the project and its optional dependencies,
    then switch back to the original directory.

    :param project_root: Path to the project root directory where pyproject.toml is located.
    :param libs: List of optional pip extra dependencies (e.g., ['examples', 'dev']).
    """
    # Save the current working directory
    original_dir = os.getcwd()

    try:
        # Change directory to the project root
        os.chdir(project_root)

        # If libs are specified, install them
        if libs:
            libs_str = ','.join(libs)
            os.system(f'{sys.executable} -m pip install -q .[{libs_str}]')

        # Install the project itself
        os.system(f'{sys.executable} -m pip install -q .')
    finally:
        # Switch back to the original directory after installation
        os.chdir(original_dir)


def show_result(filename):
    print (f'\n  {filename}')
    show(rasterio.open(filename))
