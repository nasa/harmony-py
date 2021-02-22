from base64 import b64encode
from enum import Enum
import re
from urllib.parse import urlparse

import requests


Environment = Enum('Environment', ['SBX', 'SIT', 'UAT', 'PROD'])

Hostnames = {
    Environment.SBX: 'harmony.sbx.earthdata.nasa.gov',
    Environment.SIT: 'harmony.sit.earthdata.nasa.gov',
    Environment.UAT: 'harmony.uat.earthdata.nasa.gov',
    Environment.PROD: 'harmony.earthdata.nasa.gov',
}


class SpecialSession(requests.Session):
    """Temporary requests Session which adds Basic auth for EDl."""
    EDL_URL_PATTERN = r""".*urs\.earthdata\.nasa\.gov$"""

    def __init__(self, user, pwd):
        super().__init__()
        creds = b64encode(f"{user}:{pwd}".encode('utf-8')).decode('utf-8')
        self.auth_header = f'Basic {creds}'

    def _edl_url(self, url: str) -> bool:
        """Determine if the given URL is for Earthdata Login."""
        hostname = urlparse(url).hostname
        return re.fullmatch(self.EDL_URL_PATTERN, hostname) is not None

    def rebuild_auth(self, prepared_request, response):
        if self._edl_url(prepared_request.url):
            prepared_request.headers['Authorization'] = self.auth_header
        else:
            prepared_request.headers.pop('Authorization', None)


class Collection():
    """The identity of a CMR Collection."""

    def __init__(self, id: str):
        """Constructs a Collection instance from a CMR Collection ID.

        Parameters
        ----------
        id: CMR Collection ID

        Returns
        -------
        A Collection instance
        """
        self.id = id


class Request():
    def __init__(self, collection: Collection, spatial: dict = None, temporal: dict = None):
        self.collection = collection
        self.spatial = spatial
        self.temporal = temporal
        # NOTE: The format is temporary until HARMONY-708:
        #       https://bugs.earthdata.nasa.gov/browse/HARMONY-708
        self.format = 'image/tiff'

    def is_valid(self) -> bool:
        return (
            (self.spatial is None or (('ll' in self.spatial) and
                                      ('ur' in self.spatial) and
                                      (self.spatial['ll'][0] < self.spatial['ur'][0]) and
                                      (self.spatial['ll'][0] >= -90.0) and
                                      (self.spatial['ur'][0] <= 90.0) and
                                      (self.spatial['ll'][1] < self.spatial['ur'][1]) and
                                      (self.spatial['ll'][1] >= -180.0) and
                                      (self.spatial['ur'][1] <= 180.0)))
            and
            (self.temporal is None or (('start' in self.temporal) and
                                       ('stop' in self.temporal) and
                                       (self.temporal['start'] < self.temporal['stop'])))
        )

    def error_messages(self) -> [str]:
        return ['Hi']


class Client():
    def __init__(self, env: Environment = Environment.UAT):
        self.hostname: str = Hostnames[env]

    def _url(self, request: Request) -> str:
        return (f'https://{self.hostname}/{request.collection.id}'
                '/ogc-api-coverages/1.0.0/collections/all/coverage/rangeset')

    def _params(self, request: Request) -> dict:
        params = {}
        params['subset'] = (self._spatial_subset_params(request)
                            + self._temporal_subset_params(request))
        params['format']: request.format

        return params

    def _spatial_subset_params(self, request: Request) -> list:
        if request.spatial:
            lat_lower, lon_left = request.spatial['ll']
            lat_upper, lon_right = request.spatial['ur']
            return [
                f'lat({lat_lower}:{lat_upper})',
                f'lon({lon_left}:{lon_right})'
            ]
        else:
            return []

    def _temporal_subset_params(self, request: Request) -> list:
        if request.temporal:
            s = request.temporal.get('start', None)
            if s:
                s = s.isoformat()
            e = request.temporal.get('stop', None)
            if e:
                e = e.isoformat()
            return [f'time("{s}":"{e}")']
        else:
            return []

    def submit(self, request: Request, user=None, pwd=None):
        with SpecialSession(user, pwd) as session:
            response = session.get(self._url(request), params=self._params(request))
            if response.ok:
                return response.json()
            else:
                response.raise_for_status()
