import pytest
from requests_futures.sessions import FuturesSession

from harmony_py.auth import _authenticate, _is_edl_hostname, authenticate, BadAuthentication, \
                            MissingCredentials, SessionWithHeaderRedirection

#
### auth._is_edl_hostname()
#

@pytest.mark.parametrize('hostname,expected', [
    ('uat.urs.earthdata.nasa.gov', True),
    ('urs.earthdata.nasa.gov', True),
    ('example.gov', False),
    ('earthdata.nasa.gov', False),
    ('urs.earthdata.nasa.gov.badactor.com', False)
])
def test__is_edl_hostname(hostname, expected):
    assert _is_edl_hostname(hostname) is expected

#
### auth._authentication()
#

def test__authentication_no_args():
    with pytest.raises(MissingCredentials) as exc_info:
        session = _authenticate()
    assert 'Authentication: No credentials found.' in str(exc_info.value)


def test__authentication_netrc():
    session = _authenticate(netrc_file=True)
    assert session.auth is None


def test__authentication_with_username(mocker):
    mocker.patch('harmony_py.auth.getpass', return_value='bar')
    session = _authenticate(username='foo')
    assert session.auth == ('foo', 'bar')


def test__authentication_with_username_password():
    session = _authenticate(username='foo', password='bar')
    assert session.auth == ('foo', 'bar')

#
### auth.authentication()
#

def test_authentication_no_args():
    with pytest.raises(MissingCredentials) as exc_info:
        session = authenticate(verify=True)
    assert 'Authentication: No credentials found.' in str(exc_info.value)


@pytest.fixture
def futuressessions_mocker(mocker):
    def _futuresessions_mocker(status_code):
        FuturesSession_mock = mocker.PropertyMock()
        FuturesSession_mock.get().result().configure_mock(status_code=status_code)
        return FuturesSession_mock
    
    return _futuresessions_mocker


def test_authentication(mocker, futuressessions_mocker):
    for status_code, should_error in [(200, False), (401, True), (500, True)]:
        fsm = futuressessions_mocker(status_code)
        mocker.patch('harmony_py.auth.FuturesSession', return_value=fsm)

        if should_error:
            with pytest.raises(BadAuthentication) as exc_info:
                futures_session = authenticate(netrc_file=True, verify=True)
            if status_code == 401:
                assert 'Authentication: incorrect or missing credentials' in str(exc_info.value)
            elif status_code == 500:
                assert 'Authentication: An unknown error occurred' in str(exc_info.value)
        else:
            futures_session = authenticate(netrc_file=True, verify=True)
            assert futures_session is fsm

#
### auth.SessionWithHeaderRedirection()
#

def test_SessionWithHeaderRedirection_with_no_edl(mocker):
    preparedrequest_mock = mocker.PropertyMock()
    preparedrequest_props = {'url': 'https://www.example.gov',
                              'headers': {'Authorization': 'lorem ipsum'}}
    preparedrequest_mock.configure_mock(**preparedrequest_props)

    response_mock = mocker.PropertyMock()
    response_mock.request.configure_mock(url='https://www.othersite.gov')

    mocker.patch('harmony_py.auth.PreparedRequest', return_value=preparedrequest_mock)
    mocker.patch('harmony_py.auth.Response', return_value=response_mock)

    session_with_creds = SessionWithHeaderRedirection(username='foo', password='bar')
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

    mocker.patch('harmony_py.auth.PreparedRequest', return_value=preparedrequest_mock)
    mocker.patch('harmony_py.auth.Response', return_value=response_mock)

    session_with_creds = SessionWithHeaderRedirection(username='foo', password='bar')
    session_with_creds.rebuild_auth(preparedrequest_mock, response_mock)

    assert preparedrequest_mock.url == preparedrequest_props['url'] \
           and 'Authorization' in preparedrequest_mock.headers
