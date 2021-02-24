from base64 import b64encode
from enum import Enum
from math import inf
import re
from typing import List
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
        self.validations = [
            (lambda s: s is None or 'll' in s, 'Spatial parameter is missing the lower-left coordinate'),
            (lambda s: s is None or 'ur' in s, 'Spatial parameter is missing the upper-right coordinate'),
            (lambda s: s is None or s.get('ll', (inf, inf))[0] < s.get('ur', (-inf, -inf))[0], 'Southern latitude must be less than Northern latitude'),
            (lambda s: s is None or s.get('ll', (inf, inf))[0] >= -90.0, 'Southern latitude must be greater than -90.0'),
            (lambda s: s is None or s.get('ur', (inf, inf))[0] >= -90.0, 'Northern latitude must be greater than -90.0'),
            (lambda s: s is None or s.get('ll', (inf, inf))[0] <= 90.0, 'Southern latitude must be less than 90.0'),
            (lambda s: s is None or s.get('ur', (inf, inf))[0] <= 90.0, 'Northern latitude must be less than 90.0'),
            (lambda s: s is None or s.get('ll', (inf, inf))[1] < s.get('ur', (-inf, -inf))[1], 'Western longitude must be less than Eastern longitude'),
            (lambda s: s is None or s.get('ll', (inf, inf))[1] >= -180.0, 'Western longitude must be greater than -180.0'),
            (lambda s: s is None or s.get('ur', (inf, inf))[1] >= -180.0, 'Eastern longitude must be greater than -180.0'),
            (lambda s: s is None or s.get('ll', (inf, inf))[1] <= 180.0, 'Western longitude must be less than 180.0'),
            (lambda s: s is None or s.get('ur', (inf, inf))[1] <= 180.0, 'Eastern longitude must be less than 180.0'),
        ]

    def is_valid(self) -> bool:
        return (
            all([v(self.spatial) for v, _ in self.validations])
            and
            (self.temporal is None or (('start' in self.temporal) and
                                       ('stop' in self.temporal) and
                                       (self.temporal['start'] < self.temporal['stop'])))
        )

    def error_messages(self) -> List[str]:
        return [m for v, m in self.validations if not v(self.spatial)]


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
