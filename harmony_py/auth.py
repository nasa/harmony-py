from getpass import getpass
import re
from urllib.parse import urlparse

from concurrent.futures import ThreadPoolExecutor
from requests import Session
from requests.models import PreparedRequest, Response
from requests.utils import get_netrc_auth
from requests_futures.sessions import FuturesSession
from typing import cast, Optional

from .config import Config


cfg = Config()


def _is_edl_hostname(hostname: str) -> bool:
    """
    Determine if a hostname matches an EDL hostname.

    Parameters:
        hostname (str): A fully-qualified domain name (FQDN).

    Returns:
        (boolean): True if the hostname is an EDL hostname, else False.
    """
    edl_hostname_pattern = r'.*urs\.earthdata\.nasa\.gov$'
    return re.fullmatch(edl_hostname_pattern, hostname, flags=re.IGNORECASE) is not None


class MissingCredentials(Exception):
    pass


class BadAuthentication(Exception):
    pass


class SessionWithHeaderRedirection(Session):
    """Modify Authorization headers in accordance with Earthdata Login (EDL) common usage.

    Example:
        session = SessionWithHeaderRedirection(username, password)

    Parameters:
        username (str, optional): An EDL username.
        password (str, optional): An EDL password.
    """

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None) -> None:
        super().__init__()
        if username and password:
            self.auth = (username, password)
        else:
            self.auth = None

    def rebuild_auth(self, prepared_request: PreparedRequest, response: Response) -> None:
        """
        Override Session.rebuild_auth. Strips the Authorization header if neither
        original URL nor redirected URL belong to an Earthdata Login (EDL) host. Also
        allows the default requests behavior of searching for relevant .netrc
        credentials if and only if a username and password weren't provided during
        object instantiation.

        Parameters:
            prepared_request (:obj:`PreparedRequest`): Object for the redirection
            destination.
            response (:obj:`PreparedRequest`): Object for the where we just came from.

        Returns:
            (boolean): True if the hostname is an EDL hostname, else False.
        """

        headers = prepared_request.headers
        redirect_hostname = cast(str, urlparse(prepared_request.url).hostname)
        original_hostname = cast(str, urlparse(response.request.url).hostname)

        if 'Authorization' in headers \
                and (original_hostname != redirect_hostname) \
                and not _is_edl_hostname(redirect_hostname):
            del headers['Authorization']

        if self.auth is None:
            # .netrc might have more auth for us on our new host.
            new_auth = get_netrc_auth(prepared_request.url) if self.trust_env else None
            if new_auth is not None:
                prepared_request.prepare_auth(new_auth)

        return


def _authenticate(username: Optional[str] = None, password: Optional[str] = None,
                  netrc_file: Optional[bool] = False) -> Session:
    """
    Create a requests session for authenticated HTTP calls.
    Attempts to create an authenticated session in the following order:
    1) If ``username`` and ``password`` are not None, create a session.
    2) If ``username`` is specified but not ``password``, prompt user for a password and create a
    session.
    3) If ``netrc_file`` is True, rely on the automatic behavior of requests to find relevant
    credentials in a .netrc file.
    4) Attempt to read a username and password from environment variables, either from the system
    or from a .env file to return a session.

    Parameters:
        username (str, optional): The EDL username.
        password (str, optional): The EDL password.
        netrc_file (bool, optional): Whether a .netrc file should be preferred for credentials.

    Returns:
        (:obj:`SessionWithHeaderRedirection`): The authenticated requests session.

    :raises MissingCredentials: No credentials were specified or found.
    """

    if username and password:
        return SessionWithHeaderRedirection(username, password)
    elif username and not password:
        password = getpass()
        return SessionWithHeaderRedirection(username, password)
    elif netrc_file:
        return SessionWithHeaderRedirection()
    else:
        if cfg.EDL_USERNAME and cfg.EDL_PASSWORD:
            return SessionWithHeaderRedirection(cfg.EDL_USERNAME, cfg.EDL_PASSWORD)
        else:
            raise MissingCredentials('Authentication: No credentials found.')


def authenticate(username: Optional[str] = None, password: Optional[str] = None,
                 netrc_file: Optional[bool] = False,
                 verify: Optional[bool] = True) -> Session:
    """
    Create are requests-futures session for authenticated HTTP calls after optionally verifying
    credentials.
    Attempts to create an authenticated session in the following order:
    1) If ``username`` and ``password`` are not None, create a session.
    2) If ``username`` is specified but not ``password``, prompt user for a password and create a
    session.
    3) If ``netrc_file`` is True, rely on the automatic behavior of requests to find relevant
    credentials in a .netrc file.
    4) Attempt to read a username and password from environment variables, either from the system
    or from a .env file to return a session.

    Parameters:
        username (str, optional): The EDL username.
        password (str, optional): The EDL password.
        netrc_file (bool, optional): Whether a .netrc file should be preferred for credentials.
        verify (bool, optional): Whether EDL credentials will be verified.

    Returns:
        (:obj:`SessionWithHeaderRedirection`): The authenticated requests session.

    :raises MissingCredentials: No credentials were specified or found.
    :raises BadAuthentication: Incorrect credentials or unknown error.
    """
    edl_verification_url = cfg.EDL_VERIFICATION_URL
    num_workers = int(cfg.NUM_REQUESTS_WORKERS)

    session = _authenticate(username=username, password=password, netrc_file=netrc_file)
    futures_session = FuturesSession(session=session,
                                     executor=ThreadPoolExecutor(max_workers=num_workers))

    if not verify:
        return futures_session
    else:
        result = (futures_session.get(edl_verification_url)).result()
        if result.status_code == 200:
            return futures_session
        elif result.status_code == 401:
            raise BadAuthentication('Authentication: incorrect or missing credentials during '
                                    'credential verification.')
        else:
            raise BadAuthentication('Authentication: An unknown error occurred during credential '
                                    f'verification: HTTP {result.status_code}')


# if __name__ == "__main__":
#     x = _authenticate(username='foo')
#     print('')

# if __name__ == "__main__":
#     from concurrent.futures import ThreadPoolExecutor
#     from requests_futures.sessions import FuturesSession

#     url = 'https://harmony.uat.earthdata.nasa.gov/jobs'
#     s = FuturesSession(session=authenticate(netrc_file=True),
#                        executor=ThreadPoolExecutor(max_workers=cfg.NUM_REQUESTS_WORKERS))
#     r = (s.get(url)).result()

#     if r.status_code == 200:
#         print('authentication successful')
#     elif r.status_code == 401:
#         print('incorrect or missing credentials')
#     else:
#         print(f'An unknown error has occurred during authentication: HTTP {r.status_code}')
