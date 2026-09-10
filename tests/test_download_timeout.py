"""Offline coverage for download connection and read timeouts."""

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread
from unittest.mock import MagicMock
import io

import pytest
import requests
from urllib3.exceptions import ReadTimeoutError

from harmony.client import Client


@pytest.mark.parametrize('timeout', [None, 10, (2, 30), (2, None)])
@pytest.mark.parametrize('opendap', [False, True])
def test_download_timeout_reaches_request(tmp_path, timeout, opendap):
    client = Client(should_validate_auth=False, download_timeout=timeout)
    session = MagicMock()
    client.session = session
    response = MagicMock()
    response.raw = io.BytesIO(b'data')
    response.__enter__.return_value = response
    method = session.post if opendap else session.get
    method.return_value = response
    url = 'https://opendap.example/data.nc?dap4.ce=x' if opendap else 'https://example/data.nc'
    try:
        result = client.download(url, directory=str(tmp_path)).result(timeout=5)
        assert method.call_args.kwargs['timeout'] == timeout
        assert method.call_args.kwargs['headers'] == {'Accept-Encoding': 'identity'}
        assert method.call_args.kwargs['stream'] is True
        assert method.call_args.kwargs['data'] == ({'dap4.ce': 'x'} if opendap else None)
        assert (tmp_path / 'data.nc').read_bytes() == b'data'
        assert result == str(tmp_path / 'data.nc')
        response.raise_for_status.assert_called_once()
        response.__exit__.assert_called_once()
    finally:
        client.executor.shutdown(wait=True)


@pytest.mark.parametrize('timeout', [None, (2, 30)])
def test_existing_download_is_not_requested(tmp_path, timeout):
    (tmp_path / 'data.nc').write_bytes(b'existing')
    client = Client(should_validate_auth=False, download_timeout=timeout)
    client.session = MagicMock()
    try:
        result = client.download('https://example/data.nc', str(tmp_path)).result(timeout=5)
        assert result == str(tmp_path / 'data.nc')
        client.session.get.assert_not_called()
        assert (tmp_path / 'data.nc').read_bytes() == b'existing'
    finally:
        client.executor.shutdown(wait=True)


def test_connect_timeout_reaches_future(tmp_path):
    client = Client(should_validate_auth=False, download_timeout=(1, 3))
    client.session = MagicMock()
    client.session.get.side_effect = requests.exceptions.ConnectTimeout('connection stalled')
    try:
        future = client.download('https://example/data.nc', str(tmp_path))
        with pytest.raises(requests.exceptions.ConnectTimeout):
            future.result(timeout=5)
        assert not (tmp_path / 'data.nc').exists()
    finally:
        client.executor.shutdown(wait=True)


@contextmanager
def stalled_server(send_headers):
    """Release blocked handlers before cleanup, even when a timeout regression fails."""
    release = Event()
    entered = Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if send_headers:
                self.send_response(200)
                self.send_header('Content-Length', '10')
                self.end_headers()
                self.wfile.write(b'part')
                self.wfile.flush()
            entered.set()
            release.wait(timeout=10)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/data.nc', entered
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize('send_headers', [False, True])
def test_stalled_download_releases_worker(tmp_path, send_headers, monkeypatch):
    monkeypatch.setenv('NUM_REQUESTS_WORKERS', '1')
    client = Client(should_validate_auth=False, download_timeout=(0.2, 0.2))
    client.session = requests.Session()
    client.session.trust_env = False
    try:
        with stalled_server(send_headers) as (url, entered):
            future = client.download(url, str(tmp_path))
            assert entered.wait(timeout=5)
            # Requests handles the response headers; urllib3 reads the streamed raw body.
            with pytest.raises((requests.exceptions.ReadTimeout, ReadTimeoutError)):
                future.result(timeout=5)
            assert client.executor.submit(lambda: 'available').result(timeout=5) == 'available'
    finally:
        client.session.close()
        client.executor.shutdown(wait=True)


@pytest.mark.parametrize('entry_point', ['job', 'results', 'intermediate'])
def test_bulk_downloads_use_client_timeout(tmp_path, entry_point, monkeypatch):
    client = Client(should_validate_auth=False, download_timeout=(2, 30))
    client.session = MagicMock()
    response = MagicMock()
    response.__enter__.return_value = response
    response.raw = io.BytesIO(b'data')
    client.session.get.return_value = response
    url = 'https://example/data.nc'
    try:
        if entry_point == 'job':
            monkeypatch.setattr(client, 'result_urls', lambda *args, **kwargs: iter([url]))
            downloads = client.download_all('job-id', str(tmp_path))
        elif entry_point == 'results':
            downloads = client.download_all(
                {'links': [{'rel': 'data', 'href': url}]}, str(tmp_path)
            )
        else:
            monkeypatch.setattr(
                client,
                'submit',
                lambda _: {
                    'steps': [{'workItems': [{'inputFiles': [url], 'outputFiles': []}]}],
                },
            )
            downloads = client.download_intermediate_files('job-id', [1], directory=str(tmp_path))
        assert [future.result(timeout=5) for future in downloads] == [str(tmp_path / 'data.nc')]
        assert client.session.get.call_args.kwargs['timeout'] == (2, 30)
    finally:
        client.executor.shutdown(wait=True)


def test_default_retains_unlimited_waits(tmp_path):
    client = Client(should_validate_auth=False)
    client.session = MagicMock()
    response = client.session.get.return_value.__enter__.return_value
    response.raw = io.BytesIO(b'data')
    try:
        client.download('https://example/data.nc', str(tmp_path)).result(timeout=5)
        assert client.session.get.call_args.kwargs['timeout'] is None
    finally:
        client.executor.shutdown(wait=True)
