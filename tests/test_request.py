import datetime as dt

from hypothesis import given, settings, strategies as st
import pytest

from harmony.request import BBox, WKT, Collection, OgcBaseRequest, Request, Dimension, \
    CapabilitiesRequest, AddLabelsRequest, DeleteLabelsRequest, JobsRequest


def test_request_has_collection_with_id():
    collection = Collection('foobar')
    request = OgcBaseRequest(collection=collection)
    assert request.collection.id == 'foobar'
    assert request.is_valid()


def test_transformation_request_has_collection_with_id():
    collection = Collection('foobar')
    request = Request(collection)
    assert request.collection.id == 'foobar'


def test_request_with_only_a_collection():
    request = Request(collection=Collection('foobar'))
    assert request.is_valid()


def test_request_with_skip_preview_false():
    request = Request(collection=Collection('foobar'), skip_preview=False)
    assert request.is_valid()
    assert request.skip_preview is not None and request.skip_preview == False


def test_request_with_skip_preview_true():
    request = Request(collection=Collection('foobar'), skip_preview=True)
    assert request.is_valid()
    assert request.skip_preview is not None and request.skip_preview == True


def test_request_defaults_to_skip_preview_false():
    request = Request(collection=Collection('foobar'))
    assert not request.skip_preview


def test_request_with_ignore_errors_false():
    request = Request(collection=Collection('foobar'), ignore_errors=False)
    assert request.is_valid()
    assert request.ignore_errors is not None and request.ignore_errors == False


def test_request_with_ignore_errors_true():
    request = Request(collection=Collection('foobar'), ignore_errors=True)
    assert request.is_valid()
    assert request.ignore_errors is not None and request.ignore_errors == True


def test_request_defaults_to_ignore_errors_false():
    request = Request(collection=Collection('foobar'))
    assert not request.ignore_errors


@settings(max_examples=100)
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


@pytest.mark.parametrize('key, value', [
    ('spatial', WKT('POINT(0 51.48)')),
    ('spatial', WKT('LINESTRING(30 10, 10 30, 40 40)')),
    ('spatial', WKT('POLYGON((30 10, 40 40, 20 40, 10 20, 30 10))')),
    ('spatial', WKT('POLYGON((35 10, 45 45, 15 40, 10 20, 35 10),(20 30, 35 35, 30 20, 20 30))')),
    ('spatial', WKT('MULTIPOINT((10 40), (40 30), (20 20), (30 10))')),
    ('spatial', WKT('MULTILINESTRING((10 10, 20 20, 10 40),(40 40, 30 30, 40 20, 30 10))')),
    ('spatial', WKT('MULTIPOLYGON(((30 20, 45 40, 10 40, 30 20)),((15 5, 40 10, 10 20, 5 10, 15 5)))')),
])
def test_request_spatial_wkt(key, value):
    request = Request(Collection('foo'), **{key: value})
    assert request.is_valid()


@settings(max_examples=100)
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


@settings(max_examples=100)
@given(min=st.one_of(st.floats(allow_infinity=True), st.integers()),
       max=st.one_of(st.floats(allow_infinity=True), st.integers()))
def test_request_dimensions(min, max):
    dimension = Dimension('foo', min, max)
    request = Request(
        collection=Collection('foobar'),
        dimensions=[dimension],
    )

    if request.is_valid():
        assert len(request.dimensions) == 1
        min_actual = request.dimensions[0].min
        max_actual = request.dimensions[0].max
        assert min == min_actual
        assert max == max_actual


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


@pytest.mark.parametrize('value', [
    [Dimension('foo', 0, -100.0)],
    [Dimension('foo', 0, -100.0), Dimension('bar', 50.0, 0)],
    [Dimension('foo', -100.0, 0), Dimension('bar', 50.0, 0)],
    [Dimension(name='bar', max=25, min=125.0)]
])
def test_request_dimensions_error_messages(value):
    message = 'Dimension minimum value must be less than or equal to the maximum value'
    request = Request(Collection('foo'), **{'dimensions': value})
    messages = request.error_messages()

    assert not request.is_valid()
    assert message in messages


@pytest.mark.parametrize('key, value, message', [
    ('spatial', WKT('BBOX(-140,20,-50,60)'), 'WKT BBOX(-140,20,-50,60) is invalid'),
    ('spatial', WKT('APOINT(0 51.48)'), 'WKT APOINT(0 51.48) is invalid'),
    ('spatial', WKT('CIRCULARSTRING(0 0, 1 1, 1 0)'), 'WKT CIRCULARSTRING(0 0, 1 1, 1 0) is invalid'),
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
    ('shape', './pyproject.toml',
     ['The provided shape path "./pyproject.toml" has extension "toml" which is not recognized.  '
      + 'Valid file extensions: [json, geojson, kml, shz, zip]']),
])
def test_request_shape_file_error_message(key, value, messages):
    request = Request(Collection('foo'), **{key: value})

    assert not request.is_valid()
    assert request.error_messages() == messages


def test_request_destination_url_error_message():
    request = Request(Collection('foo'), destination_url='http://somesite.com')
    messages = request.error_messages()

    assert not request.is_valid()
    assert 'Destination URL must be an S3 location' in messages


def test_collection_capabilities_without_coll_identifier():
    request = CapabilitiesRequest(capabilities_version='2')
    messages = request.error_messages()

    assert not request.is_valid()
    assert 'Must specify either collection_id or short_name for CapabilitiesRequest' in messages


def test_collection_capabilities_two_coll_identifier():
    request = CapabilitiesRequest(collection_id='C1234-PROV',
                                  short_name='foobar',
                                  capabilities_version='2')
    messages = request.error_messages()

    assert not request.is_valid()
    assert 'CapabilitiesRequest cannot have both collection_id and short_name values' in messages


def test_collection_capabilities_request_coll_id():
    request = CapabilitiesRequest(collection_id='C1234-PROV')
    assert request.is_valid()


def test_collection_capabilities_request_shortname():
    request = CapabilitiesRequest(short_name='foobar')
    assert request.is_valid()


def test_collection_capabilities_request_coll_id_version():
    request = CapabilitiesRequest(collection_id='C1234-PROV',
                                  capabilities_version='2')
    assert request.is_valid()


def test_collection_capabilities_request_shortname_version():
    request = CapabilitiesRequest(short_name='foobar',
                                  capabilities_version='2')
    assert request.is_valid()


def test_valid_add_labels_request():
    request = AddLabelsRequest(labels=['label1', 'label2'],
                               job_ids=['job_1', 'job_2'],)
    assert request.is_valid()


def test_add_labels_request_invalid_arguments():
    with pytest.raises(TypeError, match=".*got an unexpected keyword argument 'job_labels'"):
        AddLabelsRequest(job_labels=['label1'])


def test_add_labels_request_missing_labels():
    with pytest.raises(TypeError, match=".*missing 1 required keyword-only argument: 'labels'"):
        AddLabelsRequest(job_ids=['job_123'])


def test_add_labels_request_missing_job_ids():
    with pytest.raises(TypeError, match=".*missing 1 required keyword-only argument: 'job_ids'"):
        AddLabelsRequest(labels=['label1'])


def test_add_labels_request_missing_all_arguments():
    with pytest.raises(TypeError, match=".*missing 2 required keyword-only arguments: 'labels' and 'job_ids'"):
        AddLabelsRequest()


def test_valid_delete_labels_request():
    request = DeleteLabelsRequest(labels=['label1', 'label2'],
                               job_ids=['job_1', 'job_2'],)
    assert request.is_valid()


def test_delete_labels_request_invalid_arguments():
    with pytest.raises(TypeError, match=".*got an unexpected keyword argument 'job_labels'"):
        DeleteLabelsRequest(job_labels=['label1'])


def test_delete_labels_request_missing_labels():
    with pytest.raises(TypeError, match=".*missing 1 required keyword-only argument: 'labels'"):
        DeleteLabelsRequest(job_ids=['job_123'])


def test_delete_labels_request_missing_job_ids():
    with pytest.raises(TypeError, match=".*missing 1 required keyword-only argument: 'job_ids'"):
        DeleteLabelsRequest(labels=['label1'])


def test_delete_labels_request_missing_all_arguments():
    with pytest.raises(TypeError, match=".*missing 2 required keyword-only arguments: 'labels' and 'job_ids'"):
        DeleteLabelsRequest()


def test_valid_get_jobs_request():
    request = JobsRequest()
    assert request.is_valid()


def test_valid_get_jobs_request_with_page_limit():
    request = JobsRequest(page=1, limit=10)
    assert request.is_valid()


def test_valid_get_jobs_request_with_all_params():
    request = JobsRequest(page=1, limit=10, labels=['foo'])
    assert request.is_valid()


def test_valid_get_jobs_request_with_labels_in_string():
    request = JobsRequest(labels='foo')
    assert request.is_valid()


def test_valid_get_jobs_request_with_multiple_labels():
    request = JobsRequest(labels=['foo', 'bar'])
    assert request.is_valid()


def test_valid_get_jobs_request_with_multiple_labels_in_string():
    request = JobsRequest(labels='foo,bar')
    assert request.is_valid()


def test_get_jobs_request_with_invalid_argument():
    with pytest.raises(TypeError, match=".*got an unexpected keyword argument 'page_num'"):
        JobsRequest(page_num=1)

def test_request_with_pixel_subset_false():
    request = Request(collection=Collection('foobar'), pixel_subset=False)
    assert request.is_valid()
    assert request.pixel_subset is not None and request.pixel_subset == False


def test_request_with_pixel_subset_true():
    request = Request(collection=Collection('foobar'), pixel_subset=True)
    assert request.is_valid()
    assert request.pixel_subset is not None and request.pixel_subset == True


def test_request_defaults_to_pixel_subset_none():
    request = Request(collection=Collection('foobar'))
    assert request.pixel_subset is None

def test_request_with_pixel_subset_invalid():
    request = Request(collection=Collection('foobar'), pixel_subset='invalid')
    messages = request.error_messages()
    assert not request.is_valid()
    assert 'pixel_subset must be a boolean (True or False)' in messages


def test_request_with_service_id():
    request = Request(collection=Collection('foobar'), service_id='S123-PROV')
    assert request.is_valid()
    assert request.service_id == 'S123-PROV'


def test_request_with_average():
    request = Request(collection=Collection('foobar'), average='time')
    assert request.is_valid()
    assert request.average == 'time'