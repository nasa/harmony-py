import getpass
import netrc
import requests

from config import Config


cfg = Config()


class SessionWithHeaderRedirection(requests.Session):
    """Override requests.Session.rebuild_auth to maintain headers when redirected.

    Example:
    >>> session = SessionWithHeaderRedirection(username, password)
    """

    def __init__(self, username, password):
        super().__init__()
        self.auth = (username, password)

    # Overrides from the library to keep headers when redirected to or from
    # the NASA auth host.
    def rebuild_auth(self, prepared_request, response):
        """
        Override of requests.Session.rebuild_auth.
        """
        headers = prepared_request.headers
        url = prepared_request.url
 
        if 'Authorization' in headers:
            original_parsed = requests.utils.urlparse(response.request.url)
            redirect_parsed = requests.utils.urlparse(url)
 
            if (original_parsed.hostname != redirect_parsed.hostname) and \
                    redirect_parsed.hostname != cfg.AUTH_HOST and \
                    original_parsed.hostname != cfg.AUTH_HOST:
                del headers['Authorization']
 
        return


def authenticate(username=None, password=None, netrc_file=None):
    """
    Create a requests session for authenticated HTTP calls.
    Attempts to create an authenticated session has the following order:
    1) If ``username`` and ``password`` have been specified, use those to return a session.
    2) If ``username`` is specified but not ``password``, prompt user for a password and then use
    those those to return a session.
    3) If ``netrc`` is specified, attempt to read a .netrc file at that location to retrieve
    username and password, then use those to return a session session.
    4) Attempt to read the .netrc file for username and password at its default location in order
    to return a session. If this fails, continue.
    5) Attempt to read a username and password from environment variables, either from the system
    or from a .env file to return a session.

    Parameters
    ----------
    username : string, optional
        The EDL username.
    password : string, optional
        The EDL password.
    netrc_file : string, optional
        The location of a .netrc file.

    Returns
    -------
    object
        The authenticated requests session.
    """
    if username is not None and password is not None:
        return SessionWithHeaderRedirection(username, password)
    elif username is not None and password is None:
        password = getpass.getpass()
        return SessionWithHeaderRedirection(username, password)
    elif netrc_file is not None:
        try:
            username, _, password = netrc.netrc(netrc_file).authenticators(endpoint)
            return SessionWithHeaderRedirection(username, password)
        except (FileNotFoundError, TypeError):
            print('.netrc file not found; this will be replaced with logging.')
    else:
        try:
            username, _, password = netrc.netrc().authenticators(endpoint)
            return SessionWithHeaderRedirection(username, password)
        except (FileNotFoundError, TypeError):
            print('.netrc file not found in default location; verbose logging can indicate a missing netrc.')
        if cfg.EDL_USERNAME is not None and cfg.EDL_PASSWORD is not None:
            return SessionWithHeaderRedirection(cfg.EDL_USERNAME, cfg.EDL_PASSWORD)
        else:
            print('No credentials were found; replace with logging.')

