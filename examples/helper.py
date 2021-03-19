import sys
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


def show_result(filename):
    print (f'\n  {filename}')
    show(rasterio.open(filename))
