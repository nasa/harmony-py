import datetime as dt

import pytest

from harmony_py.harmony import Client, Collection, Request


# When a user supplies a lat lon bounding box data structure to the
# library, it performs a bounding box query against the Harmony
# coverages API

def test_with_bounding_box():
    request = Request(
        collection=Collection(id='C1940468263-POCLOUD'),
        spatial={
            'll': (40, -107),
            'ur': (42, -105)
        }
    )

    client = Client()
    job_id = client.submit(request)

    assert job_id is not None


# When a user supplies a temporal range data structure to the library,
# it performs a bounding box query against the Harmony coverages API
# Test cases: omitted start date, omitted end date, start and end
# supplied

@pytest.mark.skip
def test_with_temporal_range():
    request = Request(
        collection=Collection(id='C1940468263-POCLOUD'),
        temporal={
            'start': dt.date(2020, 6, 1),
            'stop': dt.date(2020, 6, 30)
        },
    )

    client = Client()
    job_id = client.submit(request)

    assert job_id is not None


# Test combinations

@pytest.mark.skip
def test_with_bounding_box_and_temporal_range():
    request = Request(
        collection=Collection(id='C1940468263-POCLOUD'),
        spatial={
            'll': (40, -107),
            'ur': (42, -105)
        },
        temporal={
            'start': dt.date(2020, 6, 1),
            'stop': dt.date(2020, 6, 30)
        },
    )

    client = Client()
    job_id = client.submit(request)

    assert job_id is not None
