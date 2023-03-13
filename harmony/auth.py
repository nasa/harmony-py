"""Earthdata Login Authorization extensions to the ``requests`` package.

This module defines two functions that enable seamless integration between
the ``requests`` module and NASA Earthdata Login. The ``create_session`` function
constructs a ``requests.Session`` that will correctly handle the OAuth redirect
'dance' that is necessary to authenticate a user. The ``validate_auth`` function
checks that the authentication credentials are valid, and can be used before
attempting to download data, for example.

The ``SessionWithHeaderRedirection``--a ``requests.Session`` subclass--is used
to perform authentication with Earthdata Login. The ``create_session`` function
uses this class and clients of the Harmony Py package do not need to use this
explicitly.
"""
import re
from typing import Optional, Tuple, cast
from urllib.parse import urlparse

from requests import Session
from requests.models import PreparedRequest, Response
from requests.utils import get_netrc_auth

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
    """The provided Earthdata Login credentials were not correctly specified."""
    pass


class BadAuthentication(Exception):
    """The provided Earthdata Login credentials were invalid."""
    pass


class SessionWithHeaderRedirection(Session):
    """A ``requests.Session`` that modifies HTTP Authorization headers in accordance
    with Earthdata Login (EDL) common usage.

    Example::

        session = SessionWithHeaderRedirection(username, password)

    Args:
        auth: A tuple of the form ('edl_username', 'edl_password')
    """

    def __init__(self, auth: Optional[Tuple[str, str]] = None, token: str = None) -> None:
        super().__init__()
        if token:
            self.headers.update({'Authorization': f'Bearer {token}'})
        elif auth:
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


def create_session(config: Config, auth: Tuple[str, str] = None, token: str = None) -> Session:
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

    Raises:
        MalformedCredentials: ``auth`` credential not in the correct format.
        BadAuthentication: Incorrect credentials or unknown error.
    """
    edl_username = config.EDL_USERNAME
    edl_password = config.EDL_PASSWORD

    if token:
        session = SessionWithHeaderRedirection(token=token)
    elif isinstance(auth, tuple) and len(auth) == 2 and all([isinstance(x, str) for x in auth]):
        session = SessionWithHeaderRedirection(auth=auth)
    elif auth is not None:
        raise MalformedCredentials('Authentication: `auth` argument requires tuple of '
                                   '(username, password).')
    elif edl_username and edl_password:
        session = SessionWithHeaderRedirection(auth=(edl_username, edl_password))
    else:
        session = SessionWithHeaderRedirection()

    return session


def validate_auth(config: Config, session: Session):
    """Validates the credentials against the EDL authentication URL."""
    if session.headers.get('Authorization') is None:
        url = config.edl_validation_url
        response = session.get(url)

        if response.status_code == 200:
            return
        elif response.status_code == 401:
            raise BadAuthentication('Authentication: incorrect or missing credentials during '
                                    'credential validation.')
        else:
            raise BadAuthentication(f'Authentication: An unknown error occurred during credential '
                                    f'validation: HTTP {response.status_code}')
