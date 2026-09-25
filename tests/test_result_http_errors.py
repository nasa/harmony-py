"""Failed result requests must not look like empty or successful data responses."""

import pytest
import requests
import responses

from harmony.client import Client, ProcessingFailedException
from harmony.request import LinkType


@pytest.fixture
def client():
    client = Client(should_validate_auth=False, check_interval=0)
    # Use a real HTTP session without retry delays; responses intercepts its transport.
    client.session = requests.Session()
    yield client
    client.session.close()
    client.executor.shutdown(wait=True)


def completed_job(http, client, job_id='test-job'):
    http.add(
        responses.POST,
        client._job_status_batch_url(),
        json={'jobStatuses': [{'jobID': job_id, 'progress': 100, 'status': 'successful'}]},
    )
    http.add(
        responses.GET,
        client._status_url(job_id),
        json={'progress': 100, 'status': 'successful', 'message': 'Complete'},
    )


@pytest.mark.parametrize('status', [401, 403, 404, 429, 500, 503])
@pytest.mark.parametrize('body_type', ['json', 'html'])
def test_get_json_preserves_http_errors(client, status, body_type):
    url = client._status_url('test-job')
    with responses.RequestsMock() as http:
        payload = (
            {'json': {'description': 'Result unavailable'}}
            if body_type == 'json'
            else {'body': '<html>Result unavailable</html>', 'content_type': 'text/html'}
        )
        http.add(responses.GET, url, status=status, **payload)
        with pytest.raises(requests.HTTPError) as caught:
            client._get_json(url)
        assert caught.value.response.status_code == status
        assert caught.value.request.url == url


@pytest.mark.parametrize('link_type', [LinkType.https, LinkType.s3])
def test_result_json_rejects_failed_final_request(client, link_type):
    with responses.RequestsMock() as http:
        completed_job(http, client)
        http.add(
            responses.GET,
            client._status_url('test-job', link_type),
            status=403,
            json={'description': 'Result access denied'},
        )
        with pytest.raises(requests.HTTPError) as caught:
            client.result_json('test-job', link_type=link_type)
        assert caught.value.response.status_code == 403


@pytest.mark.parametrize('page_number', [1, 2])
def test_result_urls_does_not_silently_truncate_on_failed_page(client, page_number):
    first = client._status_url('test-job')
    second = first + '&page=2'
    with responses.RequestsMock() as http:
        completed_job(http, client)
        if page_number == 2:
            http.add(
                responses.GET,
                first,
                json={
                    'links': [
                        {'rel': 'data', 'href': 'https://data.example.test/first.nc'},
                        {'rel': 'next', 'href': second},
                    ]
                },
            )
        http.add(
            responses.GET,
            first if page_number == 1 else second,
            status=503,
            json={'description': 'Temporarily unavailable'},
        )
        urls = client.result_urls('test-job')
        if page_number == 2:
            assert next(urls) == 'https://data.example.test/first.nc'
        with pytest.raises(requests.HTTPError) as caught:
            next(urls)
        assert caught.value.response.status_code == 503


def test_successful_json_and_pagination_remain_unchanged(client):
    first = client._status_url('test-job')
    second = first + '&page=2'
    with responses.RequestsMock() as http:
        completed_job(http, client)
        http.add(
            responses.GET,
            first,
            json={
                'links': [
                    {'rel': 'data', 'href': 'https://data.example.test/first.nc'},
                    {'rel': 'next', 'href': second},
                ]
            },
        )
        http.add(
            responses.GET,
            second,
            json={
                'links': [
                    {'rel': 'data', 'href': 'https://data.example.test/second.nc'},
                ]
            },
        )
        assert list(client.result_urls('test-job')) == [
            'https://data.example.test/first.nc',
            'https://data.example.test/second.nc',
        ]


def test_successful_non_json_body_still_raises_decode_error(client):
    url = client._status_url('test-job')
    with responses.RequestsMock() as http:
        http.add(responses.GET, url, status=200, body='not JSON')
        with pytest.raises(requests.exceptions.JSONDecodeError):
            client._get_json(url)


def test_failed_job_metadata_can_still_be_retrieved(client):
    url = client._status_url('failed-job')
    with responses.RequestsMock() as http:
        http.add(
            responses.POST,
            client._job_status_batch_url(),
            json={'jobStatuses': [{'jobID': 'failed-job', 'progress': 100, 'status': 'failed'}]},
        )
        metadata = {'progress': 100, 'status': 'failed', 'message': 'Processing failed'}
        http.add(responses.GET, url, json=metadata)
        http.add(responses.GET, url, json=metadata)
        assert client.result_json('failed-job') == metadata
