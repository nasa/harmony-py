import pytest
from requests_futures.sessions import FuturesSession

from harmony.auth import (_is_edl_hostname, validate_auth, create_session, validate_auth,
                          BadAuthentication, MalformedCredentials, SessionWithHeaderRedirection)
from harmony.config import Config


@pytest.fixture
def config():
    return Config()


@pytest.fixture
def futuressessions_mocker(mocker):
    def _futuresessions_mocker(status_code):
        FuturesSession_mock = mocker.PropertyMock()
        FuturesSession_mock.get().result().configure_mock(status_code=status_code)
        return FuturesSession_mock
    
    return _futuresessions_mocker


def test_authentication_no_args_no_validate(config):
    session = create_session(config)
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


@pytest.mark.parametrize('status_code,should_error', 
                         [(200, False), (401, True), (500, True)])
def test_authentication(status_code, should_error, config, mocker, futuressessions_mocker):
    fsm = futuressessions_mocker(status_code)
    mocker.patch('harmony.auth.FuturesSession', return_value=fsm)

    if should_error:
        with pytest.raises(BadAuthentication) as exc_info:
            futures_session = create_session(config)
            validate_auth(config, futures_session)
        if status_code == 401:
            assert 'Authentication: incorrect or missing credentials' in str(exc_info.value)
        elif status_code == 500:
            assert 'Authentication: An unknown error occurred' in str(exc_info.value)
    else:
        futures_session = create_session(config)
        validate_auth(config, futures_session)
        assert futures_session is fsm


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
