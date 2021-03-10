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



def download_and_show_results(harmony_client, harmony_job):
    status_url = harmony_job['links'][0]['href']
    print('Waiting for the job to finish')

    with harmony_client._session() as session:
        while harmony_job['status'] != 'successful':
            harmony_job = session.get(status_url).result().json()
            print(f"Job is {harmony_job['status']}: {harmony_job['progress']}%")
            sleep(3)
    
        print('Downloading results')
        for result in [link for link in harmony_job['links'] if link['type'] == 'image/tiff']:
            with open(result['title'], 'wb') as f:
                print(f"  {result['title']}")
                f.write(session.get(result['href']).result().content)
                show(rasterio.open(result['title']))
