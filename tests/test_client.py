import datetime as dt

import pytest
import responses

from harmony_py.harmony import Client, Collection, Request


def expected_url(collection_id):
    return (f'https://harmony.uat.earthdata.nasa.gov/{collection_id}'
            '/ogc-api-coverages/1.0.0/collections/all/coverage/rangeset')


def expected_json(collection_id, job_id):
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
        'request': ('https://harmony.uat.earthdata.nasa.gov/{collection_id}/ogc-api-coverages/1.0.0'
                    '/collections/all/coverage/rangeset'
                    '?subset=lat(52%3A77)'
                    '&subset=lon(-165%3A-140)'
                    '&subset=time(%222010-01-01T00%3A00%3A00%22%3A%222020-12-30T00%3A00%3A00%22)'),
        'numInputGranules': 32,
        'jobID': '21469294-d6f7-42cc-89f2-c81990a5d7f4'
    }


@responses.activate
def test_with_bounding_box():
    collection = Collection(id='C1940468263-POCLOUD')
    request = Request(
        collection=collection,
        spatial={
            'll': (40, -107),
            'ur': (42, -105)
        }
    )
    job_id = '21469294-d6f7-42cc-89f2-c81990a5d7f4'
    responses.add(responses.GET, expected_url(collection.id),
                  status=200, json=expected_json(collection.id, job_id))

    job = Client().submit(request)

    assert job is not None


# When a user supplies a temporal range data structure to the library,
# it performs a bounding box query against the Harmony coverages API
# Test cases: omitted start date, omitted end date, start and end
# supplied

@responses.activate
def test_with_temporal_range():
    collection = Collection(id='C1940468263-POCLOUD')
    request = Request(
        collection=collection,
        temporal={
            'start': dt.date(2020, 6, 1),
            'stop': dt.date(2020, 6, 30)
        },
    )
    job_id = '21469294-d6f7-42cc-89f2-c81990a5d7f4'
    responses.add(responses.GET, expected_url(collection.id),
                  status=200, json=expected_json(collection.id, job_id))

    job = Client().submit(request)

    assert job is not None


@responses.activate
def test_with_bounding_box_and_temporal_range():
    collection = Collection(id='C1940468263-POCLOUD')
    request = Request(
        collection=collection,
        spatial={
            'll': (40, -107),
            'ur': (42, -105)
        },
        temporal={
            'start': dt.date(2020, 6, 1),
            'stop': dt.date(2020, 6, 30)
        },
    )
    job_id = '21469294-d6f7-42cc-89f2-c81990a5d7f4'
    responses.add(responses.GET, expected_url(collection.id),
                  status=200, json=expected_json(collection.id, job_id))

    job = Client().submit(request)

    assert job is not None
