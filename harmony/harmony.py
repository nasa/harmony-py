from typing import NamedTuple
from enum import Enum
from typing import List, Optional, Tuple

from requests_futures.sessions import FuturesSession

from harmony.auth import create_session, validate_auth, SessionWithHeaderRedirection
from harmony.config import Config


Environment = Enum('Environment', ['SBX', 'SIT', 'UAT', 'PROD'])

Hostnames = {
    Environment.SBX: 'harmony.sbx.earthdata.nasa.gov',
    Environment.SIT: 'harmony.sit.earthdata.nasa.gov',
    Environment.UAT: 'harmony.uat.earthdata.nasa.gov',
    Environment.PROD: 'harmony.earthdata.nasa.gov',
}


class Collection:
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


class BBox(NamedTuple):
    """A bounding box specified by western & eastern longitude, southern & northern latitude constraints."""
    w: float
    s: float
    e: float
    n: float

    def __repr__(self) -> str:
        return f'BBox: West:{self.w}, South:{self.s}, East:{self.e}, North:{self.n}'


class Request:
    def __init__(self, collection: Collection, spatial: BBox = None, temporal: dict = None):
        self.collection = collection
        self.spatial = spatial
        self.temporal = temporal
        # NOTE: The format is temporary until HARMONY-708:
        #       https://bugs.earthdata.nasa.gov/browse/HARMONY-708
        self.format = 'image/tiff'
        self.spatial_validations = [
            (lambda bb: bb.s < bb.n, 'Southern latitude must be less than Northern latitude'),
            (lambda bb: bb.s >= -90.0, 'Southern latitude must be greater than -90.0'),
            (lambda bb: bb.n >= -90.0, 'Northern latitude must be greater than -90.0'),
            (lambda bb: bb.s <= 90.0, 'Southern latitude must be less than 90.0'),
            (lambda bb: bb.n <= 90.0, 'Northern latitude must be less than 90.0'),
            (lambda bb: bb.w < bb.e, 'Western longitude must be less than Eastern longitude'),
            (lambda bb: bb.w >= -180.0, 'Western longitude must be greater than -180.0'),
            (lambda bb: bb.e >= -180.0, 'Eastern longitude must be greater than -180.0'),
            (lambda bb: bb.w <= 180.0, 'Western longitude must be less than 180.0'),
            (lambda bb: bb.e <= 180.0, 'Eastern longitude must be less than 180.0'),
        ]
        self.temporal_validations = [
            (lambda tr: 'start' in tr or 'stop' in tr,
             'When included in the request, the temporal range should include a start or stop attribute.'),
            (lambda tr: tr['start'] < tr['stop'] if 'start' in tr and 'stop' in tr else True,
             'The temporal range\'s start must be earlier than its stop datetime.')
        ]

    def is_valid(self) -> bool:
        return \
            (self.spatial is None or all([v(self.spatial) for v, _ in self.spatial_validations])) \
            and (self.temporal is None or all([v(self.temporal) for v, _ in self.temporal_validations]))

    def error_messages(self) -> List[str]:
        spatial_msgs = []
        temporal_msgs = []
        if self.spatial:
            spatial_msgs = [m for v, m in self.spatial_validations if not v(self.spatial)]
        if self.temporal:
            temporal_msgs = [m for v, m in self.temporal_validations if not v(self.temporal)]

        return spatial_msgs + temporal_msgs


class Client:
    def __init__(
        self,
        *,
        auth: Optional[Tuple[str, str]] = None,
        should_validate_auth: bool = True,
        env: Environment = Environment.UAT,
    ):
        """Creates a Harmony Client that can be used to interact with Harmony.

        Parameters:
            auth (Tuple[str, str]): A tuple of the format ('edl_username', 'edl_password')
            should_validate_auth (bool, optional): Whether EDL credentials will be validated.
        """
        self.config = Config()
        self.hostname: str = Hostnames[env]
        self.session = None
        self.auth = auth

        if should_validate_auth:
            validate_auth(self.config, self._session())

    def _session(self):
        if self.session is None:
            self.session = create_session(self.config, self.auth)
        return self.session

    def _url(self, request: Request) -> str:
        """Constructs the URL from the given request."""
        return (
            f'https://{self.hostname}/{request.collection.id}'
            '/ogc-api-coverages/1.0.0/collections/all/coverage/rangeset'
        )

    def _params(self, request: Request) -> dict:
        """Creates a dictionary of request query parameters from the given request."""
        params = {}
        params['subset'] = self._spatial_subset_params(request) + self._temporal_subset_params(
            request
        )
        params['format']: request.format

        return params

    def _spatial_subset_params(self, request: Request) -> list:
        """Creates a dictionary of spatial subset query parameters."""
        if request.spatial:
            lon_left, lat_lower, lon_right, lat_upper = request.spatial
            return [f'lat({lat_lower}:{lat_upper})', f'lon({lon_left}:{lon_right})']
        else:
            return []

    def _temporal_subset_params(self, request: Request) -> list:
        """Creates a dictionary of temporal subset query parameters."""
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

    def submit(self, request: Request):
        """Submits a request to Harmony and returns the Harmony job details."""
        with self._session() as session:
            response = session.get(self._url(request), params=self._params(request)).result()
            if response.ok:
                return response.json()
            else:
                response.raise_for_status()
