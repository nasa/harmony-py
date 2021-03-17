import datetime as dt
import json
import urllib.parse

import dateutil.parser
import pytest
from requests_futures.sessions import FuturesSession
import responses

from harmony.harmony import BBox, Client, Collection, Request


def expected_submit_url(collection_id, variables='all'):
    return (f'https://harmony.uat.earthdata.nasa.gov/{collection_id}'
            f'/ogc-api-coverages/1.0.0/collections/{variables}/coverage/rangeset')


def expected_status_url(job_id):
    return f'https://harmony.uat.earthdata.nasa.gov/jobs/{job_id}'


def expected_full_submit_url(request):
    async_params = ['forceAsync=True']

    spatial_params = []
    if request.spatial:
        w, s, e, n = request.spatial
        spatial_params = [f'subset=lat({s}:{n})', f'subset=lon({w}:{e})']

    temporal_params = []
    if request.temporal:
        start = request.temporal['start']
        stop = request.temporal['stop']
        temporal_params = [f'subset=time("{start.isoformat()}":"{stop.isoformat()}")']

    query_params = '&'.join(async_params + spatial_params + temporal_params)
    if request.format is not None:
        query_params += f'&format{request.format}'

    return f'{expected_submit_url(request.collection.id)}?{query_params}'


def expected_job(collection_id, job_id):
    return {
        'username': 'rfeynman',
        'status': 'running',
        'message': 'The job is being processed',
        'progress': 0,
        'createdAt': '2021-02-19T18:47:31.291Z',
        'updatedAt': '2021-02-19T18:47:31.291Z',
        'links': [
            {
                'title': 'Job Status',
                'href': 'https://harmony.uat.earthdata.nasa.gov/jobs/{job_id)',
                'rel': 'self',
                'type': 'application/json'
            }
        ],
        'request': (
            'https://harmony.uat.earthdata.nasa.gov/{collection_id}/ogc-api-coverages/1.0.0'
            '/collections/all/coverage/rangeset'
            '?forceAsync=True'
            '&subset=lat(52%3A77)'
            '&subset=lon(-165%3A-140)'
            '&subset=time(%222010-01-01T00%3A00%3A00%22%3A%222020-12-30T00%3A00%3A00%22)'
        ),
        'numInputGranules': 32,
        'jobID': f'{job_id}'
    }


@responses.activate
def test_when_multiple_submits_it_only_authenticates_once():
    collection = Collection(id='C1940468263-POCLOUD')
    request = Request(
        collection=collection,
        spatial=BBox(-107, 40, -105, 42)
    )
    job_id = '3141592653-abcd-1234'
    auth_url = 'https://harmony.uat.earthdata.nasa.gov/jobs'
    responses.add(
        responses.GET,
        auth_url,
        status=200
    )
    responses.add(
        responses.GET,
        expected_submit_url(collection.id),
        status=200,
        json=expected_job(collection.id, job_id)
    )

    client = Client()
    client.submit(request)
    client.submit(request)

    assert len(responses.calls) == 3
    assert responses.calls[0].request.url == auth_url
    assert urllib.parse.unquote(responses.calls[0].request.url) == auth_url
    assert urllib.parse.unquote(responses.calls[1].request.url) == expected_full_submit_url(request)
    assert urllib.parse.unquote(responses.calls[2].request.url) == expected_full_submit_url(request)


@responses.activate
def test_with_bounding_box():
    collection = Collection(id='C1940468263-POCLOUD')
    request = Request(
        collection=collection,
        spatial=BBox(-107, 40, -105, 42)
    )
    job_id = '21469294-d6f7-42cc-89f2-c81990a5d7f4'
    responses.add(
        responses.GET,
        expected_submit_url(collection.id),
        status=200,
        json=expected_job(collection.id, job_id)
    )

    actual_job_id = Client(should_validate_auth=False).submit(request)

    assert len(responses.calls) == 1
    assert responses.calls[0].request is not None
    assert urllib.parse.unquote(responses.calls[0].request.url) == expected_full_submit_url(request)
    assert actual_job_id == job_id


@responses.activate
def test_with_temporal_range():
    collection = Collection(id='C1234-TATOOINE')
    request = Request(
        collection=collection,
        temporal={
            'start': dt.datetime(2010, 12, 1),
            'stop': dt.datetime(2010, 12, 31)
        },
    )
    job_id = '1234abcd-deed-9876-c001-f00dbad'
    responses.add(
        responses.GET,
        expected_submit_url(collection.id),
        status=200,
        json=expected_job(collection.id, job_id)
    )

    actual_job_id = Client(should_validate_auth=False).submit(request)

    assert len(responses.calls) == 1
    assert responses.calls[0].request is not None
    assert urllib.parse.unquote(responses.calls[0].request.url) == expected_full_submit_url(request)
    assert actual_job_id == job_id


@responses.activate
def test_with_bounding_box_and_temporal_range():
    collection = Collection(id='C333666999-EOSDIS')
    request = Request(
        collection=collection,
        spatial=BBox(-107, 40, -105, 42),
        temporal={
            'start': dt.datetime(2001, 1, 1),
            'stop': dt.datetime(2003, 3, 31)
        },
    )
    job_id = '1234abcd-1234-9876-6666-999999abcd'
    responses.add(
        responses.GET,
        expected_submit_url(collection.id),
        status=200,
        json=expected_job(collection.id, job_id)
    )

    actual_job_id = Client(should_validate_auth=False).submit(request)

    assert len(responses.calls) == 1
    assert responses.calls[0].request is not None
    assert urllib.parse.unquote(responses.calls[0].request.url) == expected_full_submit_url(request)
    assert actual_job_id == job_id


def test_with_invalid_request():
    collection = Collection(id='C333666999-EOSDIS')
    request = Request(
        collection=collection,
        spatial=BBox(-190, -100, 100, 190)
    )

    with pytest.raises(Exception):
        Client(should_validate_auth=False).submit(request)


@pytest.mark.parametrize('param,expected', [
    ({'crs': 'epsg:3141'}, 'outputcrs=epsg:3141'),
    ({'format': 'r2d2/hologram'}, 'format=r2d2/hologram'),
    ({'granule_id': ['G1', 'G2', 'G3']}, 'granuleId=G1&granuleId=G2&granuleId=G3'),
    ({'height': 200}, 'height=200'),
    ({'interpolation': 'nearest'}, 'interpolation=nearest'),
    ({'max_results': 7}, 'maxResults=7'),
    ({'scale_extent': [1.0, 2.0, 1.0, 4.0]}, 'scaleExtent=1.0,2.0,1.0,4.0'),
    ({'scale_size': [1.0, 2.0]}, 'scaleSize=1.0,2.0'),
    ({'width': 100}, 'width=100'),
])
@responses.activate
def test_request_has_query_param(param, expected):
    collection = Collection('foobar')
    request = Request(
        collection=collection,
        **param
    )
    responses.add(
        responses.GET,
        expected_submit_url(collection.id),
        status=200,
        json=expected_job(collection.id, 'abcd-1234'),
    )

    Client(should_validate_auth=False).submit(request)

    assert len(responses.calls) == 1
    assert urllib.parse.unquote(responses.calls[0].request.url).index(expected) >= 0


@pytest.mark.parametrize('variables,expected', [
    (['one'], 'one'),
    (['red_var', 'green_var', 'blue_var'], 'red_var,green_var,blue_var'),
    (['/var/with/a/path'], '%2Fvar%2Fwith%2Fa%2Fpath')
])
@responses.activate
def test_request_has_variables(variables, expected):
    collection = Collection('foobar')
    request = Request(
        collection=collection,
        variables=variables
    )
    responses.add(
        responses.GET,
        expected_submit_url(collection.id, expected),
        status=200,
        json=expected_job(collection.id, 'abcd-1234'),
    )

    Client(should_validate_auth=False).submit(request)


@responses.activate
def test_status():
    collection = Collection(id='C333666999-EOSDIS')
    job_id = '21469294-d6f7-42cc-89f2-c81990a5d7f4'
    exp_job = expected_job(collection.id, job_id)
    expected_status = {
        'status': exp_job['status'],
        'message': exp_job['message'],
        'progress': exp_job['progress'],
        'created_at': dateutil.parser.parse(exp_job['createdAt']),
        'updated_at': dateutil.parser.parse(exp_job['updatedAt']),
        'request': exp_job['request'],
        'num_input_granules': exp_job['numInputGranules']}
    responses.add(
        responses.GET,
        expected_status_url(job_id),
        status=200,
        json=exp_job
    )

    actual_status = Client(should_validate_auth=False).status(job_id)

    assert len(responses.calls) == 1
    assert responses.calls[0].request is not None
    assert urllib.parse.unquote(responses.calls[0].request.url) == expected_status_url(job_id)
    assert actual_status == expected_status



@responses.activate
def test_progress():
    collection = Collection(id='C333666999-EOSDIS')
    job_id = '21469294-d6f7-42cc-89f2-c81990a5d7f4'
    exp_job = expected_job(collection.id, job_id)
    expected_progress = int(exp_job['progress'])
    responses.add(
        responses.GET,
        expected_status_url(job_id),
        status=200,
        json=exp_job
    )

    actual_progress = Client(should_validate_auth=False).progress(job_id)

    assert len(responses.calls) == 1
    assert responses.calls[0].request is not None
    assert urllib.parse.unquote(responses.calls[0].request.url) == expected_status_url(job_id)
    assert actual_progress == expected_progress
