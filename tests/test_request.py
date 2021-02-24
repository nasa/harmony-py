from hypothesis import given, settings, strategies as st
import pytest

from harmony_py.harmony import Collection, Request


def test_request_has_collection_with_id():
    collection = Collection('foobar')

    request = Request(collection)

    assert request.collection.id == 'foobar'


def test_request_with_only_a_collection():
    request = Request(collection=Collection('foobar'))
    assert request.is_valid()


@settings(max_examples=200)
@given(key_a=st.one_of(st.none(), st.sampled_from(['ll', 'ur']), st.text()),
       key_b=st.one_of(st.none(), st.sampled_from(['ll', 'ur']), st.text()),
       tuple_a=st.tuples(st.floats(allow_infinity=True), st.floats(allow_infinity=True)),
       tuple_b=st.tuples(st.floats(allow_infinity=True), st.floats(allow_infinity=True)))
def test_request_spatial_bounding_box(key_a, key_b, tuple_a, tuple_b):
    spatial = {
        key_a: tuple_a,
        key_b: tuple_b
    }
    request = Request(
        collection=Collection('foobar'),
        spatial=spatial,
    )

    if request.is_valid():
        assert request.spatial is not None
        assert 'll' in spatial
        assert 'ur' in spatial
        assert request.spatial[key_a] == tuple_a
        assert request.spatial[key_b] == tuple_b

        lat_bottom, lon_left = request.spatial['ll']
        lat_top, lon_right = request.spatial['ur']
        assert lat_bottom < lat_top
        assert lat_bottom >= -90.0
        assert lat_top <= 90.0
        assert lon_left < lon_right
        assert lon_left >= -180.0
        assert lon_right <= 180.0


@settings(max_examples=200)
@given(key_a=st.one_of(st.none(), st.sampled_from(['start', 'stop']), st.text()),
       key_b=st.one_of(st.none(), st.sampled_from(['start', 'stop']), st.text()),
       datetime_a=st.datetimes(),
       datetime_b=st.datetimes())
def test_request_temporal_range(key_a, key_b, datetime_a, datetime_b):
    temporal = {
        key_a: datetime_a,
        key_b: datetime_b
    }
    request = Request(
        collection=Collection('foobar'),
        temporal=temporal
    )

    if request.is_valid():
        assert request.temporal is not None
        assert 'start' in request.temporal or 'stop' in request.temporal
        assert request.temporal['start'] < request.temporal['stop']


@pytest.mark.parametrize('key, value, message', [
    ('spatial', {'ur': (-10, 10)}, 'Spatial parameter is missing the lower-left coordinate'),
    ('spatial', {'ll': (-10, 10)}, 'Spatial parameter is missing the upper-right coordinate'),
    ('spatial', {'ll': (-10, 10), 'ur': (-20, 20)}, 'Southern latitude must be less than Northern latitude'),
    ('spatial', {'ll': (-100, 10), 'ur': (20, 20)}, 'Southern latitude must be greater than -90.0'),
    ('spatial', {'ll': (-110, 10), 'ur': (-100, 20)}, 'Northern latitude must be greater than -90.0'),
    ('spatial', {'ll': (100, 10), 'ur': (110, 20)}, 'Southern latitude must be less than 90.0'),
    ('spatial', {'ll': (-10, 10), 'ur': (100, 20)}, 'Northern latitude must be less than 90.0'),
    ('spatial', {'ll': (-10, 10), 'ur': (20, -20)}, 'Western longitude must be less than Eastern longitude'),
    ('spatial', {'ll': (10, -190), 'ur': (20, 20)}, 'Western longitude must be greater than -180.0'),
    ('spatial', {'ll': (10, -200), 'ur': (20, -190)}, 'Eastern longitude must be greater than -180.0'),
    ('spatial', {'ll': (10, 10), 'ur': (20, 190)}, 'Eastern longitude must be less than 180.0'),
    ('spatial', {'ll': (10, 190), 'ur': (20, 200)}, 'Western longitude must be less than 180.0'),
])
def test_request_error_messages(key, value, message):
    request = Request(Collection('foo'), **{key: value})
    messages = request.error_messages()

    assert not request.is_valid()
    assert message in messages


def test_request_has_format():
    # NOTE: This test is temporary until HARMONY-708:
    #       https://bugs.earthdata.nasa.gov/browse/HARMONY-708
    request = Request(collection=Collection('foobar'))
    assert request.format is not None
