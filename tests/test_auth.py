import pytest
import responses
from requests.auth import _basic_auth_str

from harmony import CapabilitiesRequest, Client

from harmony.auth import (
    _is_edl_hostname,
    create_session,
    validate_auth,
    BadAuthentication,
    MalformedCredentials,
    SessionWithHeaderRedirection,
)
from harmony.config import Config


class Object(object):
    pass


@pytest.fixture
def config():
    return Config()


def test_authentication_no_args_no_validate():
    fake_config = Object()
    fake_config.EDL_USERNAME = None
    fake_config.EDL_PASSWORD = None
    session = create_session(fake_config)
    assert session.auth is None


@pytest.mark.parametrize(
    'hostname,expected',
    [
        ('uat.urs.earthdata.nasa.gov', True),
        ('urs.earthdata.nasa.gov', True),
        ('example.gov', False),
        ('earthdata.nasa.gov', False),
        ('urs.earthdata.nasa.gov.badactor.com', False),
    ],
)
def test__is_edl_hostname(hostname, expected):
    assert _is_edl_hostname(hostname) is expected


@pytest.mark.parametrize(
    'auth',
    [
        (None,),
        ('username'),
        ('username',),
        ('username', 333),
        (999, 'secret'),
    ],
)
def test_authentication_with_malformed_auth(auth, config, mocker):
    with pytest.raises(MalformedCredentials) as exc_info:
        session = create_session(config, auth=auth)
        validate_auth(config, session)
    assert 'Authentication: `auth` argument requires tuple' in str(exc_info.value)


@responses.activate
@pytest.mark.parametrize('status_code,should_error', [(200, False), (401, True), (500, True)])
def test_authentication(status_code, should_error, config, mocker):
    auth_url = 'https://harmony.earthdata.nasa.gov/jobs'
    responses.add(responses.GET, auth_url, status=status_code)
    if should_error:
        with pytest.raises(BadAuthentication) as exc_info:
            actual_session = create_session(config)
            validate_auth(config, actual_session)
        if status_code == 401:
            assert 'Authentication: incorrect or missing credentials' in str(exc_info.value)
        elif status_code == 500:
            assert 'Authentication: An unknown error occurred' in str(exc_info.value)
    else:
        actual_session = create_session(config)
        validate_auth(config, actual_session)
        assert actual_session is not None


@responses.activate
@pytest.mark.parametrize('token', [None, 'example-token'])
def test_explicit_token_takes_precedence_over_netrc(tmp_path, monkeypatch, token):
    netrc_path = tmp_path / 'netrc'
    netrc_path.write_text(
        'machine harmony.earthdata.nasa.gov login example-user password example-password\n'
        'machine urs.earthdata.nasa.gov login example-user password example-password\n'
        'machine example.com login other-user password other-password\n'
    )
    monkeypatch.setenv('NETRC', str(netrc_path))
    monkeypatch.delenv('EDL_USERNAME', raising=False)
    monkeypatch.delenv('EDL_PASSWORD', raising=False)
    url = 'https://harmony.earthdata.nasa.gov/capabilities'
    edl_url = 'https://urs.earthdata.nasa.gov/authorize'
    responses.add(responses.GET, url, status=302, headers={'Location': edl_url})
    responses.add(responses.GET, edl_url, status=302, headers={'Location': 'https://example.com/'})
    responses.add(responses.GET, 'https://example.com/', status=200, json={'ok': True})
    client = Client(token=token, should_validate_auth=False)
    try:
        assert client.submit(CapabilitiesRequest(collection_id='example')) == {'ok': True}
        expected = f'Bearer {token}' if token else _basic_auth_str('example-user', 'example-password')
        assert responses.calls[0].request.headers['Authorization'] == expected
        assert responses.calls[1].request.headers['Authorization'] == expected
        if token:
            assert 'Authorization' not in responses.calls[2].request.headers
        else:
            assert responses.calls[2].request.headers['Authorization'] == _basic_auth_str(
                'other-user', 'other-password'
            )
        assert client._session().trust_env is True
    finally:
        client._session().close()
        client.executor.shutdown(wait=True)


def test_SessionWithHeaderRedirection_with_no_edl(mocker):
    preparedrequest_mock = mocker.PropertyMock()
    preparedrequest_props = {
        'url': 'https://www.example.gov',
        'headers': {'Authorization': 'lorem ipsum'},
    }
    preparedrequest_mock.configure_mock(**preparedrequest_props)

    response_mock = mocker.PropertyMock()
    response_mock.request.configure_mock(url='https://www.othersite.gov')

    mocker.patch('harmony.auth.PreparedRequest', return_value=preparedrequest_mock)
    mocker.patch('harmony.auth.Response', return_value=response_mock)

    session_with_creds = SessionWithHeaderRedirection(auth=('foo', 'bar'))
    session_with_creds.rebuild_auth(preparedrequest_mock, response_mock)

    assert (
        preparedrequest_mock.url == preparedrequest_props['url']
        and 'Authorization' not in preparedrequest_mock.headers
    )


def test_SessionWithHeaderRedirection_with_edl(mocker):
    preparedrequest_mock = mocker.PropertyMock()
    preparedrequest_props = {
        'url': 'https://uat.urs.earthdata.nasa.gov',
        'headers': {'Authorization': 'lorem ipsum'},
    }
    preparedrequest_mock.configure_mock(**preparedrequest_props)

    response_mock = mocker.PropertyMock()
    response_mock.request.configure_mock(url='https://www.othersite.gov')

    mocker.patch('harmony.auth.PreparedRequest', return_value=preparedrequest_mock)
    mocker.patch('harmony.auth.Response', return_value=response_mock)

    session_with_creds = SessionWithHeaderRedirection(auth=('foo', 'bar'))
    session_with_creds.rebuild_auth(preparedrequest_mock, response_mock)

    assert (
        preparedrequest_mock.url == preparedrequest_props['url']
        and 'Authorization' in preparedrequest_mock.headers
    )
