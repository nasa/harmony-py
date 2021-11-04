import datetime as dt

from hypothesis import given, settings, strategies as st
import pytest

from harmony.harmony import BBox, Collection, Request


def test_request_has_collection_with_id():
    collection = Collection('foobar')

    request = Request(collection)

    assert request.collection.id == 'foobar'


def test_request_with_only_a_collection():
    request = Request(collection=Collection('foobar'))
    assert request.is_valid()


@settings(max_examples=200)
@given(west=st.floats(allow_infinity=True),
       south=st.floats(allow_infinity=True),
       east=st.floats(allow_infinity=True),
       north=st.floats(allow_infinity=True))
def test_request_spatial_bounding_box(west, south, east, north):
    spatial = BBox(west, south, east, north)
    request = Request(
        collection=Collection('foobar'),
        spatial=spatial,
    )

    if request.is_valid():
        assert request.spatial is not None
        w, s, e, n = request.spatial
        assert w == west
        assert s == south
        assert e == east
        assert n == north

        assert south <= north

        assert south >= -90.0
        assert north >= -90.0
        assert south <= 90.0
        assert north <= 90.0

        assert west >= -180.0
        assert east >= -180.0
        assert west <= 180.0
        assert east <= 180.0


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
        if 'start' in request.temporal and 'stop' in request.temporal:
            assert request.temporal['start'] < request.temporal['stop']


@pytest.mark.parametrize('key, value, message', [
    ('spatial', BBox(10, -10, 20, -20), 'Southern latitude must be less than or equal to Northern latitude'),
    ('spatial', BBox(10, -100, 20, 20), 'Southern latitude must be greater than -90.0'),
    ('spatial', BBox(10, -110, 20, -100), 'Northern latitude must be greater than -90.0'),
    ('spatial', BBox(10, 100, 20, 110), 'Southern latitude must be less than 90.0'),
    ('spatial', BBox(10, 10, 20, 100), 'Northern latitude must be less than 90.0'),
    ('spatial', BBox(-190, 10, 20, 20), 'Western longitude must be greater than -180.0'),
    ('spatial', BBox(-200, 10, -190, 20), 'Eastern longitude must be greater than -180.0'),
    ('spatial', BBox(10, 10, 190, 20), 'Eastern longitude must be less than 180.0'),
    ('spatial', BBox(190, 10, 200, 20), 'Western longitude must be less than 180.0'),
])
def test_request_spatial_error_messages(key, value, message):
    request = Request(Collection('foo'), **{key: value})
    messages = request.error_messages()

    assert not request.is_valid()
    assert message in messages


@pytest.mark.parametrize('key, value, message', [
    (
        'temporal', {
            'foo': None
        },
        ('When included in the request, the temporal range should include a '
         'start or stop attribute.')
    ), (
        'temporal', {
            'start': dt.datetime(1969, 7, 20),
            'stop': dt.datetime(1941, 12, 7)
        },
        'The temporal range\'s start must be earlier than its stop datetime.'
    )
])
def test_request_temporal_error_messages(key, value, message):
    request = Request(Collection('foo'), **{key: value})
    messages = request.error_messages()

    assert not request.is_valid()
    assert message in messages


def test_request_valid_shape():
    request = Request(Collection('foo'), shape='./examples/asf_example.json')
    messages = request.error_messages()
    assert request.is_valid()
    assert messages == []


@pytest.mark.parametrize('key, value, messages', [
    ('shape', './tests/', ['The provided shape path "./tests/" is not a file']),
    ('shape', './setup.py',
     ['The provided shape path "./setup.py" has extension "py" which is not recognized.  '
      + 'Valid file extensions: [json, geojson, kml, shz, zip]']),
])
def test_request_shape_file_error_message(key, value, messages):
    request = Request(Collection('foo'), **{key: value})

    assert not request.is_valid()
    assert request.error_messages() == messages
