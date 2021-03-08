from typing import NamedTuple
from typing import List, Optional, Tuple

from requests_futures.sessions import FuturesSession

from harmony.auth import create_session, validate_auth, SessionWithHeaderRedirection
from harmony.config import Config, Environment


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
    """A bounding box specified by western & eastern longitude,
    southern & northern latitude constraints in degrees.

    Example:
      An area bounded by latitudes 30N and 60N and longitudes
      130W and 100W:

          >>> spatial = BBox(-130, 30, -100, 60)

      Important: When specified positionally, the parameters must
      be given in order: west, south, east, north.

      Alternatively, one can explicitly set each bound using the
      single-letter for each bound:

          >>> spatial = BBox(n=60, s=30, e=-100, w=-130)

      Print the spatial bounds:

          >>> print(spatial)
          BBox: West:-130, South:30, East:-100, North:60

    Parameters:
    -----------
    w: The western longitude bounds (degrees)
    s: The souther latitude bounds (degrees)
    e: The easter longitude bounds (degrees)
    n: The northern latitude bounds (degrees)

    Returns:
    A BBox instance with the provided bounds.
    """
    w: float
    s: float
    e: float
    n: float

    def __repr__(self) -> str:
        return f'BBox: West:{self.w}, South:{self.s}, East:{self.e}, North:{self.n}'


class Request:
    """A Harmony request with the CMR collection and various parameters expressing how the data is
    to be transformed.

    Parameters:
    -----------
    collection: The CMR collection that should be queried
    spatial: Bounding box spatial constraints on the data
    temporal: Date/time constraints on the data

    Returns:
    --------
    A Harmony Request instance
    """
    def __init__(self, collection: Collection, spatial: BBox = None, temporal: dict = None):
        self.collection = collection
        self.spatial = spatial
        self.temporal = temporal
        # NOTE: The format is temporary until HARMONY-708:
        #       https://bugs.earthdata.nasa.gov/browse/HARMONY-708
        self.format: str = 'image/tiff'
        self.spatial_validations = [
            (lambda bb: bb.s < bb.n, 'Southern latitude must be less than Northern latitude'),
            (lambda bb: bb.s >= -90.0, 'Southern latitude must be greater than -90.0'),
            (lambda bb: bb.n >= -90.0, 'Northern latitude must be greater than -90.0'),
            (lambda bb: bb.s <= 90.0, 'Southern latitude must be less than 90.0'),
            (lambda bb: bb.n <= 90.0, 'Northern latitude must be less than 90.0'),
            (lambda bb: bb.w >= -180.0, 'Western longitude must be greater than -180.0'),
            (lambda bb: bb.e >= -180.0, 'Eastern longitude must be greater than -180.0'),
            (lambda bb: bb.w <= 180.0, 'Western longitude must be less than 180.0'),
            (lambda bb: bb.e <= 180.0, 'Eastern longitude must be less than 180.0'),
        ]
        self.temporal_validations = [
            (lambda tr: 'start' in tr or 'stop' in tr,
             ('When included in the request, the temporal range should include a '
              'start or stop attribute.')),
            (lambda tr: tr['start'] < tr['stop'] if 'start' in tr and 'stop' in tr else True,
             'The temporal range\'s start must be earlier than its stop datetime.')
        ]

    def is_valid(self) -> bool:
        """Determines if the request and its parameters are valid."""
        return \
            (self.spatial is None or all([v(self.spatial)
                                          for v, _ in self.spatial_validations])) \
            and \
            (self.temporal is None or all([v(self.temporal)
                                           for v, _ in self.temporal_validations]))

    def error_messages(self) -> List[str]:
        """A list of error messages, if any, for the request."""
        spatial_msgs = []
        temporal_msgs = []
        if self.spatial:
            spatial_msgs = [m for v, m in self.spatial_validations if not v(self.spatial)]
        if self.temporal:
            temporal_msgs = [m for v, m in self.temporal_validations if not v(self.temporal)]

        return spatial_msgs + temporal_msgs


class Client:
    """A Harmony client object which can be used to submit requests to Harmony.

    Examples:

    With no arguments

        >>> client = Client()

    will create a Harmony client that will either use the EDL_USERNAME & EDL_PASSWORD
    environment variables to authenticate with Earthdata Login, or will use the credentials
    in the user's `.netrc` file, if one is available.

    To explicitly include the user's credentials:

        >>> client = Client(auth=('rfeynman', 'quantumf1eld5'))

    By default, the Client will validate the provided credentials immediately. This can be
    disabled by passing `should_validate_auth=False`.
    """
    def __init__(
        self,
        *,
        auth: Optional[Tuple[str, str]] = None,
        should_validate_auth: bool = True,
        env: Environment = Environment.UAT,
    ):
        """Creates a Harmony Client that can be used to interact with Harmony.

        Parameters:
            auth : A tuple of the format ('edl_username', 'edl_password')
            should_validate_auth: Whether EDL credentials will be validated.
        """
        self.config = Config(env)
        self.hostname: str = self.config.hostname
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
        params['subset'] = (self._spatial_subset_params(request)
                            + self._temporal_subset_params(request))
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
            t = request.temporal
            start = t['start'].isoformat() if 'start' in t else None
            stop = t['stop'].isoformat() if 'stop' in t else None
            start_quoted = f'"{start}"' if start else ''
            stop_quoted = f'"{stop}"' if start else ''
            return [f'time({start_quoted}:{stop_quoted})']
        else:
            return []

    def submit(self, request: Request) -> Optional[dict]:
        """Submits a request to Harmony and returns the Harmony job details."""
        if not request.is_valid():
            msgs = ', '.join(request.error_messages())
            raise Exception(f"Cannot submit an invalid request: [{msgs}]")

        job = None
        with self._session() as session:
            response = session.get(self._url(request), params=self._params(request)).result()
            if response.ok:
                job = response.json()
            else:
                response.raise_for_status()

        return job
