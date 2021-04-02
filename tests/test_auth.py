import pytest
import responses

from harmony.auth import (_is_edl_hostname, create_session, validate_auth,
                          BadAuthentication, MalformedCredentials, SessionWithHeaderRedirection)
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


@pytest.mark.parametrize('hostname,expected', [
    ('uat.urs.earthdata.nasa.gov', True),
    ('urs.earthdata.nasa.gov', True),
    ('example.gov', False),
    ('earthdata.nasa.gov', False),
    ('urs.earthdata.nasa.gov.badactor.com', False)
])
def test__is_edl_hostname(hostname, expected):
    assert _is_edl_hostname(hostname) is expected


@pytest.mark.parametrize('auth', [
    (None,),
    ('username'),
    ('username',),
    ('username', 333),
    (999, 'secret'),
])
def test_authentication_with_malformed_auth(auth, config, mocker):
    with pytest.raises(MalformedCredentials) as exc_info:
        session = create_session(config, auth=auth)
        validate_auth(config, session)
    assert 'Authentication: `auth` argument requires tuple' in str(exc_info.value)


@responses.activate
@pytest.mark.parametrize('status_code,should_error',
                         [(200, False), (401, True), (500, True)])
def test_authentication(status_code, should_error, config, mocker):
    auth_url = 'https://harmony.earthdata.nasa.gov/jobs'
    responses.add(
        responses.GET,
        auth_url,
        status=status_code
    )
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


def test_SessionWithHeaderRedirection_with_no_edl(mocker):
    preparedrequest_mock = mocker.PropertyMock()
    preparedrequest_props = {'url': 'https://www.example.gov',
                             'headers': {'Authorization': 'lorem ipsum'}}
    preparedrequest_mock.configure_mock(**preparedrequest_props)

    response_mock = mocker.PropertyMock()
    response_mock.request.configure_mock(url='https://www.othersite.gov')

    mocker.patch('harmony.auth.PreparedRequest', return_value=preparedrequest_mock)
    mocker.patch('harmony.auth.Response', return_value=response_mock)

    session_with_creds = SessionWithHeaderRedirection(auth=('foo', 'bar'))
    session_with_creds.rebuild_auth(preparedrequest_mock, response_mock)

    assert preparedrequest_mock.url == preparedrequest_props['url'] \
           and 'Authorization' not in preparedrequest_mock.headers


def test_SessionWithHeaderRedirection_with_edl(mocker):
    preparedrequest_mock = mocker.PropertyMock()
    preparedrequest_props = {'url': 'https://uat.urs.earthdata.nasa.gov',
                             'headers': {'Authorization': 'lorem ipsum'}}
    preparedrequest_mock.configure_mock(**preparedrequest_props)

    response_mock = mocker.PropertyMock()
    response_mock.request.configure_mock(url='https://www.othersite.gov')

    mocker.patch('harmony.auth.PreparedRequest', return_value=preparedrequest_mock)
    mocker.patch('harmony.auth.Response', return_value=response_mock)

    session_with_creds = SessionWithHeaderRedirection(auth=('foo', 'bar'))
    session_with_creds.rebuild_auth(preparedrequest_mock, response_mock)

    assert preparedrequest_mock.url == preparedrequest_props['url'] \
           and 'Authorization' in preparedrequest_mock.headers
