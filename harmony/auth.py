import re
from typing import cast, Optional, Tuple
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

from requests import Session
from requests.models import PreparedRequest, Response
from requests.utils import get_netrc_auth
from requests_futures.sessions import FuturesSession

from harmony.config import Config


def _is_edl_hostname(hostname: str) -> bool:
    """
    Determine if a hostname matches an EDL hostname.

    Args:
        hostname: A fully-qualified domain name (FQDN).

    Returns:
        True if the hostname is an EDL hostname, else False.
    """
    edl_hostname_pattern = r'.*urs\.earthdata\.nasa\.gov$'
    return re.fullmatch(edl_hostname_pattern, hostname, flags=re.IGNORECASE) is not None


class MalformedCredentials(Exception):
    pass


class BadAuthentication(Exception):
    pass


class SessionWithHeaderRedirection(Session):
    """Modify Authorization headers in accordance with Earthdata Login (EDL) common usage.

    Example:
        session = SessionWithHeaderRedirection(username, password)

    Args:
        auth: A tuple of the form ('edl_username', 'edl_password')
    """

    def __init__(self, auth: Optional[Tuple[str, str]] = None) -> None:
        super().__init__()
        if auth:
            self.auth = auth
        else:
            self.auth = None

    def rebuild_auth(self, prepared_request: PreparedRequest, response: Response) -> None:
        """
        Override Session.rebuild_auth. Strips the Authorization header if neither
        original URL nor redirected URL belong to an Earthdata Login (EDL) host. Also
        allows the default requests behavior of searching for relevant .netrc
        credentials if and only if a username and password weren't provided during
        object instantiation.

        Args:
            prepared_request: Object for the redirection destination.
            response: Object for the where we just came from.
        """

        headers = prepared_request.headers
        redirect_hostname = cast(str, urlparse(prepared_request.url).hostname)
        original_hostname = cast(str, urlparse(response.request.url).hostname)

        if ('Authorization' in headers
                and (original_hostname != redirect_hostname)
                and not _is_edl_hostname(redirect_hostname)):
            del headers['Authorization']

        if self.auth is None:
            # .netrc might have more auth for us on our new host.
            new_auth = get_netrc_auth(prepared_request.url) if self.trust_env else None
            if new_auth is not None:
                prepared_request.prepare_auth(new_auth)

        return


def create_session(config: Config, auth: Tuple[str, str] = None) -> FuturesSession:
    """Creates a configured ``requests`` session.

    Attempts to create an authenticated session in the following order:

    1) If ``auth`` is a tuple of (username, password), create a session.
    2) Attempt to read a username and password from environment variables, either from the system
       or from a .env file to return a session.
    3) Return a session that attempts to read credentials from a .netrc file.

    Args:
        config: Configuration object with EDL and authentication context
        auth: A tuple of the form ('edl_username', 'edl_password')

    Returns:
        The authenticated ``requests`` session.

    :raises MalformedCredentials: ``auth`` credential not in the correct format.
    :raises BadAuthentication: Incorrect credentials or unknown error.
    """
    cfg_edl_username = config.EDL_USERNAME
    cfg_edl_password = config.EDL_PASSWORD
    num_workers = int(config.NUM_REQUESTS_WORKERS)

    if isinstance(auth, tuple) and len(auth) == 2 and all([isinstance(x, str) for x in auth]):
        session = SessionWithHeaderRedirection(auth=auth)
    elif auth is not None:
        raise MalformedCredentials('Authentication: `auth` argument requires tuple of '
                                   '(username, password).')
    elif cfg_edl_username and cfg_edl_password:
        session = SessionWithHeaderRedirection(auth=(cfg_edl_username, cfg_edl_password))
    else:
        session = SessionWithHeaderRedirection()

    return FuturesSession(session=session, executor=ThreadPoolExecutor(max_workers=num_workers))


def validate_auth(config, session):
    """Validates the credentials against the EDL authentication URL."""
    url = config.EDL_VALIDATION_URL
    result = session.get(url).result()

    if result.status_code == 200:
        return
    elif result.status_code == 401:
        raise BadAuthentication('Authentication: incorrect or missing credentials during '
                                'credential validation.')
    else:
        raise BadAuthentication(f'Authentication: An unknown error occurred during credential '
                                f'validation: HTTP {result.status_code}')
