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


def download_and_show_results_prev(harmony_client, job_id):
    print('Waiting for the job to finish')

    status = harmony_client.status(job_id)

    while True:
        status = harmony_client.status(job_id)
        print(f"Job is {status['status']}: {status['progress']}%")
        if status['status'] == 'successful':
            break
        else:
            sleep(3)

    print('Downloading results')
    session = harmony_client._session()
    harmony_job = session.get(harmony_client._status_url(job_id)).result().json()
    print(harmony_job)
    for result in [link for link in harmony_job['links'] if link['type'] == 'image/tiff']:
        with open(result['title'], 'wb') as f:
            print(f"  {result['title']}")
            f.write(session.get(result['href']).result().content)
            show(rasterio.open(result['title']))


def download_and_show_results(harmony_client, job_id):
    print('Waiting for the job to finish')
    results = harmony_client.result_json(job_id, show_progress=True)

    print('Downloading results')
    files = harmony_client.download_all(job_id)
    for f in files:
        f.result()

    for result in [link for link in results['links'] if link['type'] == 'image/tiff']:
        with open(result['title'], 'wb') as f:
            print(f"  {result['title']}")
            show(rasterio.open(result['title']))