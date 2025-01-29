"""This module defines the main classes used to interact with Harmony.

The classes defined here are also available by importing them from the
top-level ``harmony`` package, e.g.::

    from harmony import Client, Request


Overview of the classes:


    * Collection: A CMR Collection ID

    * BBox: A bounding box (lat/lon) used in Requests

    * Request: A complete Harmony request with all criteria

    * Client: Allows submission of a Harmony Request and getting results

"""

from http.client import ResponseNotReady
import os
import shutil
import sys
from tabnanny import check
import time
import platform
from uuid import UUID
from requests import Response
from requests.exceptions import JSONDecodeError
import requests.models
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date, datetime
from enum import Enum
from typing import Any, ContextManager, IO, Iterator, List, Mapping, NamedTuple, Optional, \
    Tuple, Generator, Union
from urllib import parse

import curlify
import dateutil.parser
import progressbar
from shapely.wkt import loads
from shapely.lib import ShapelyError

from harmony.auth import create_session, validate_auth
from harmony.config import Config, Environment
from harmony import __version__ as harmony_version

DEFAULT_JOB_LABEL = "harmony-py"

progressbar_widgets = [
    ' [ Processing: ', progressbar.Percentage(), ' ] ',
    progressbar.Bar(),
    ' [', progressbar.RotatingMarker(), ']',
]


def is_wkt_valid(wkt_string: str) -> bool:
    try:
        # Attempt to load the WKT string
        loads(wkt_string)
        return True
    except (ShapelyError, ValueError) as e:
        # Handle WKT reading errors and invalid WKT strings
        print(f"Invalid WKT: {e}")
        return False


def temporal_to_edr_datetime(temporal: dict) -> str:
    datetime_format = '%Y-%m-%dT%H:%M:%SZ'

    if 'start' in temporal and temporal['start'] is not None:
        start_str = temporal['start'].strftime(datetime_format)
    else:
        start_str = '..'

    if 'stop' in temporal and temporal['stop'] is not None:
        stop_str = temporal['stop'].strftime(datetime_format)
    else:
        stop_str = '..'

    return f'{start_str}/{stop_str}'


class ProcessingFailedException(Exception):
    """Indicates a Harmony job has failed during processing"""

    def __init__(self, job_id: str, message: str):
        """Constructs the exception
        Args:
            job_id: The ID of the job that failed
            message: The reason given for the failure
        """
        super().__init__(message)
        self.job_id = job_id


class Collection:
    """The identity of a CMR Collection."""

    def __init__(self, id: str):
        """Constructs a Collection instance from a CMR Collection ID.

        Args:
            id: CMR Collection ID

        Returns:
            A Collection instance
        """
        self.id = id


class BBox(NamedTuple):
    """A bounding box specified by western & eastern longitude,
    southern & northern latitude constraints in degrees.

    Example:
      An area bounded by latitudes 30N and 60N and longitudes
      130W and 100W::

          >>> spatial = BBox(-130, 30, -100, 60)

    Important: When specified positionally, the parameters must
    be given in order: west, south, east, north.

    Alternatively, one can explicitly set each bound using the
    single-letter for each bound::

        >>> spatial = BBox(n=60, s=30, e=-100, w=-130)

    Print a readable representation of the spatial bounds::

        >>> print(spatial)
        BBox: West:-130, South:30, East:-100, North:60

    Args:
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


class WKT:
    """The Well Known Text (WKT) representation of Spatial.
    Supported WKT geometry types are:
    POINT, MULTIPOINT, POLYGON, MULTIPOLYGON, LINESTRING and MULTILINESTRING.

    Example:
        spatial=WKT('POINT(-40 10)')

        spatial=WKT('MULTIPOINT((-77 38.9),(-40 10))')

        spatial=WKT('POLYGON((-140 20, -50 20, -50 60, -140 60, -140 20))')

        spatial=WKT('MULTIPOLYGON(((10 10, 20 20, 30 10, 10 10)),((40 40, 50 50, 60 40, 40 40)))')

        spatial=WKT('LINESTRING(-155.75 19.26, -155.3 19.94)')

        spatial=WKT('MULTILINESTRING((-155.75 19.26, -155.3 19.94),(10 1, 10 30))')
    """

    def __init__(self, wkt: str):
        """Constructs a WKT instance of spatial area.

        Args:
            wkt: the WKT string

        Returns:
            A WKT instance
        """
        self.wkt = wkt


class Dimension:
    """An arbitrary dimension to subset against. A dimension can take a minimum value and a
    maximum value to to subset against.

    Example:
        Requesting the data to be subset by the dimension lev with a minimum value of 10.0
        and maximum value of 20.0::

            >>> dimension = Dimension('lev', 10.0, 20.0)

        Important: When specified positionally, the parameters must be given in the order:
        dimension name, minimum value, maximum value.

        Alternatively, one can explicitly set each value used named parameters:

            >>> dimension = Dimension(name='lev', min=10.0, max=20.0)

        Print a readable representation of the dimension::

            >>> print(dimension)
            Dimension: Name: lev, Minimum: 10.0, Maximum: 20.0

    Args:
        name: The dimension name
        min: The minimum value for the given dimension to subset against (optional)
        max: The maximum value for the given dimension to subset against (optional)

    Returns:
        A Dimension instance with the provided dimension subset values.
    """
    name: str
    min: float
    max: float

    def __init__(self, name: str, min: float = None, max: float = None):
        self.name = name
        self.min = min
        self.max = max

    def __repr__(self) -> str:
        return f'Dimension: Name: {self.name}, Minimum:{self.min}, Maximum:{self.max}'


_shapefile_exts_to_mimes = {
    'json': 'application/geo+json',
    'geojson': 'application/geo+json',
    'kml': 'application/vnd.google-earth.kml+xml',
    'shz': 'application/shapefile+zip',
    'zip': 'application/shapefile+zip',
}
_valid_shapefile_exts = ', '.join((_shapefile_exts_to_mimes.keys()))


class BaseRequest:
    """A Harmony base request with the CMR collection. It is the base class of all harmony
    requests.

    Args:
        collection: The CMR collection that should be queried

    Returns:
        A Harmony Request instance
    """

    def __init__(self,
                 *,
                 collection: Collection):
        self.collection = collection
        self.variable_name_to_query_param = {}

    def error_messages(self) -> List[str]:
        return []

    def is_valid(self) -> bool:
        """Determines if the request and its parameters are valid."""
        return len(self.error_messages()) == 0

    def parameter_values(self) -> List[Tuple[str, Any]]:
        """Returns tuples of each query parameter that has been set and its value."""
        pvs = [(param, getattr(self, variable))
               for variable, param in self.variable_name_to_query_param.items()]
        return [(p, v) for p, v in pvs if v is not None]


class Request(BaseRequest):
    """A Harmony request with the CMR collection and various parameters expressing
    how the data is to be transformed.

    Args:
        collection: The CMR collection that should be queried

        spatial: Bounding box spatial constraints on the data or Well Known Text (WKT) string
          describing the spatial constraints.

        temporal: Date/time constraints on the data provided as a dict mapping "start" and "stop"
          keys to corresponding start/stop datetime.datetime objects

        dimensions: A list of dimensions to use for subsetting the data

        extend: A list of dimensions to extend

        crs: reproject the output coverage to the given CRS.  Recognizes CRS types that can be
          inferred by gdal, including EPSG codes, Proj4 strings, and OGC URLs
          (http://www.opengis.net/def/crs/...)

        interpolation: specify the interpolation method used during reprojection and scaling

        scale_extent: scale the resulting coverage either among one axis to a given extent

        scale_size: scale the resulting coverage either among one axis to a given size

        shape: a file path to an ESRI Shapefile zip, GeoJSON file, or KML file to use for
          spatial subsetting.  Note: not all collections support shapefile subsetting

        variables: The list of variables to subset

        granule_id: The CMR Granule ID for the granule which should be retrieved

        granule_name: The granule ur or provider id for the granule(s) to be retrieved
          wildcards * (multi character match) and ? (single character match) are supported

        width: number of columns to return in the output coverage

        height: number of rows to return in the output coverage

        format: the output mime type to return

        max_results: limits the number of input granules processed in the request

        concatenate: Whether to invoke a service that supports concatenation

        skip_preview: Whether Harmony should skip auto-pausing and generating a preview for
          large jobs

        ignore_errors: if "true", continue processing a request to completion
          even if some items fail

        destination_url: Destination URL specified by the client
          (only S3 is supported, e.g. s3://my-bucket-name/mypath)

        grid: The name of the output grid to use for regridding requests. The name must
          match the UMM grid name in the CMR.

        labels: The list of labels to include for the request. By default a 'harmony-py'
          label is added to all requests unless the environment variable EXCLUDE_DEFAULT_LABEL
          is set to 'true'.

    Returns:
        A Harmony Transformation Request instance
    """

    def __init__(self,
                 collection: Collection,
                 *,
                 spatial: Union[BBox, WKT] = None,
                 temporal: Mapping[str, datetime] = None,
                 dimensions: List[Dimension] = None,
                 extend: List[str] = None,
                 crs: str = None,
                 destination_url: str = None,
                 format: str = None,
                 granule_id: List[str] = None,
                 granule_name: List[str] = None,
                 height: int = None,
                 interpolation: str = None,
                 max_results: int = None,
                 scale_extent: List[float] = None,
                 scale_size: List[float] = None,
                 shape: Optional[Tuple[IO, str]] = None,
                 variables: List[str] = ['all'],
                 width: int = None,
                 concatenate: bool = None,
                 skip_preview: bool = None,
                 ignore_errors: bool = None,
                 grid: str = None,
                 labels: List[str] = None):
        """Creates a new Request instance from all specified criteria.'
        """
        super().__init__(collection=collection)
        self.spatial = spatial
        self.temporal = temporal
        self.dimensions = dimensions
        self.extend = extend
        self.crs = crs
        self.destination_url = destination_url
        self.format = format
        self.granule_id = granule_id
        self.granule_name = granule_name
        self.height = height
        self.interpolation = interpolation
        self.max_results = max_results
        self.scale_extent = scale_extent
        self.scale_size = scale_size
        self.shape = shape
        self.variables = variables
        self.width = width
        self.concatenate = concatenate
        self.skip_preview = skip_preview
        self.ignore_errors = ignore_errors
        self.grid = grid
        self.labels = labels

        if self.is_edr_request():
            self.variable_name_to_query_param = {
                'crs': 'crs',
                'destination_url': 'destinationUrl',
                'interpolation': 'interpolation',
                'scale_extent': 'scaleExtent',
                'scale_size': 'scaleSize',
                'shape': 'shapefile',
                'granule_id': 'granuleId',
                'granule_name': 'granuleName',
                'width': 'width',
                'height': 'height',
                'format': 'f',
                'max_results': 'maxResults',
                'concatenate': 'concatenate',
                'skip_preview': 'skipPreview',
                'ignore_errors': 'ignoreErrors',
                'grid': 'grid',
                'extend': 'extend',
                'variables': 'parameter-name',
                'labels': 'label',
            }
            self.spatial_validations = [
                (lambda s: is_wkt_valid(s.wkt), f'WKT {spatial.wkt} is invalid'),
            ]
        else:
            self.variable_name_to_query_param = {
                'crs': 'outputcrs',
                'destination_url': 'destinationUrl',
                'interpolation': 'interpolation',
                'scale_extent': 'scaleExtent',
                'scale_size': 'scaleSize',
                'shape': 'shapefile',
                'granule_id': 'granuleId',
                'granule_name': 'granuleName',
                'width': 'width',
                'height': 'height',
                'format': 'format',
                'max_results': 'maxResults',
                'concatenate': 'concatenate',
                'skip_preview': 'skipPreview',
                'ignore_errors': 'ignoreErrors',
                'grid': 'grid',
                'extend': 'extend',
                'variables': 'variable',
                'labels': 'label',
            }

            self.spatial_validations = [
                (lambda bb: bb.s <= bb.n, ('Southern latitude must be less than '
                                           'or equal to Northern latitude')),
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
        self.shape_validations = [
            (lambda s: os.path.isfile(s), 'The provided shape path is not a file'),
            (lambda s: s.split('.').pop().lower() in _shapefile_exts_to_mimes,
             'The provided shape file is not a recognized type.  Valid file extensions: '
             + f'[{_valid_shapefile_exts}]'),
        ]
        self.dimension_validations = [
            (lambda dim: dim.min is None or dim.max is None or dim.min <= dim.max,
             ('Dimension minimum value must be less than or equal to the maximum value'))
        ]
        self.parameter_validations = [  # for simple, one-off validations
            (True if self.destination_url is None else self.destination_url.startswith('s3://'),
             ('Destination URL must be an S3 location'))
        ]

    def _shape_error_messages(self, shape) -> List[str]:
        """Returns a list of error message for the provided shape."""
        if not shape:
            return []
        if not os.path.exists(shape):
            return [f'The provided shape path "{shape}" does not exist']
        if not os.path.isfile(shape):
            return [f'The provided shape path "{shape}" is not a file']
        ext = shape.split('.').pop().lower()
        if ext not in _shapefile_exts_to_mimes:
            return [f'The provided shape path "{shape}" has extension "{ext}" which is not '
                    + f'recognized.  Valid file extensions: [{_valid_shapefile_exts}]']
        return []

    def is_edr_request(self) -> bool:
        """Return true if the request needs to be submitted as an EDR request,
        i.e. Spatial is WKT."""
        return isinstance(self.spatial, WKT)

    def error_messages(self) -> List[str]:
        """A list of error messages, if any, for the request."""
        spatial_msgs = []
        temporal_msgs = []
        dimension_msgs = []
        parameter_msgs = [m for v, m in self.parameter_validations if not v]
        shape_msgs = self._shape_error_messages(self.shape)
        if self.spatial:
            spatial_msgs = [m for v, m in self.spatial_validations if not v(self.spatial)]
        if self.temporal:
            temporal_msgs = [m for v, m in self.temporal_validations if not v(self.temporal)]
        if self.dimensions:
            for dim in self.dimensions:
                msgs = [m for v, m in self.dimension_validations if not v(dim)]
                if msgs:
                    dimension_msgs += msgs

        return spatial_msgs + temporal_msgs + shape_msgs + dimension_msgs + parameter_msgs


class CapabilitiesRequest(BaseRequest):
    """A Harmony request to get the harmony capabilities of a CMR collection
    Args:
        Keyword arguments with optional collection_id, short_name and capabilities_version fields
        - collection_id: The CMR collection Id that should be queried
        - short_name: The CMR collection shortName that should be queried
        - capabilities_version: the version of the collection capabilities request api

    Returns:
        A Harmony Capability Request instance
    """

    def __init__(self,
                 **request_params
                 ):

        coll_identifier = request_params.get('collection_id', request_params.get('short_name'))

        super().__init__(collection=coll_identifier)
        self.collection_id = request_params.get('collection_id')
        self.short_name = request_params.get('short_name')
        self.capabilities_version = request_params.get('capabilities_version')

        self.variable_name_to_query_param = {
            'collection_id': 'collectionid',
            'short_name': 'shortname',
            'capabilities_version': 'version',
        }

    def error_messages(self) -> List[str]:
        """A list of error messages, if any, for the request."""
        error_msgs = []
        if self.collection_id is None and self.short_name is None:
            error_msgs = [
                'Must specify either collection_id or short_name for CapabilitiesRequest'
            ]
        elif self.collection_id and self.short_name:
            error_msgs = [
                'CapabilitiesRequest cannot have both collection_id and short_name values'
            ]

        return error_msgs


class LinkType(Enum):
    """The type of URL to provide when returning links to data.

    s3: Returns an Amazon Web Services (AWS) S3 URL
    https: Returns a standard HTTP URL
    """
    s3 = 's3'
    http = 'http'
    https = 'https'


class Client:
    """A Harmony client object which can be used to submit requests to Harmony.

    Examples:

    With no arguments::

        >>> client = Client()

    will create a Harmony client that will either use the EDL_USERNAME & EDL_PASSWORD
    environment variables to authenticate with Earthdata Login, or will use the credentials
    in the user's ``.netrc`` file, if one is available.

    To explicitly include the user's credentials::

        >>> client = Client(auth=('rfeynman', 'quantumf1eld5'))

    You can also create a Harmony client using user's EDL token::

        >>> client = Client(token='myEDLTokenValue')

    By default, the Client will validate the provided credentials immediately. This can be
    disabled by passing ``should_validate_auth=False``.
    """

    zarr_download_exception_msg = 'The zarr library must be used for zarr files. '\
        'See https://github.com/nasa/harmony/blob/main/docs/Harmony%20Feature%20Examples.ipynb '\
        'for zarr library usage example.'
    zarr_download_exception = Exception(zarr_download_exception_msg)

    def __init__(
        self,
        *,
        auth: Optional[Tuple[str, str]] = None,
        should_validate_auth: bool = True,
        env: Environment = Environment.PROD,
        token: str = None,
        # How often to poll Harmony for updated information during job processing
        check_interval: float = 3.0  # in seconds
    ):
        """Creates a Harmony Client that can be used to interact with Harmony.

        Args:
            auth : A tuple of the format ('edl_username', 'edl_password')
            should_validate_auth: Whether EDL credentials will be validated.
        """
        self.config = Config(env)
        self.session = None
        self.auth = auth
        self.token = token
        self.check_interval = check_interval

        num_workers = int(self.config.NUM_REQUESTS_WORKERS)
        self.executor = ThreadPoolExecutor(max_workers=num_workers)

        if should_validate_auth:
            validate_auth(self.config, self._session())

    def _session(self):
        """Creates (if needed) and returns the Client's requests Session."""
        if self.session is None:
            if self.token:
                self.session = create_session(self.config, token=self.token)
            else:
                self.session = create_session(self.config, auth=self.auth)
        return self.session

    def _http_method(self, request: BaseRequest) -> str:
        """Returns the HTTP method to use for the given request."""
        method = 'GET' if isinstance(request, CapabilitiesRequest) else 'POST'
        return method

    def _wkt_to_edr_route(self, wkt_string: str) -> str:
        """Returns the EDR route for the given WKT string."""
        # Load the WKT string into a Shapely geometry object
        geometry = loads(wkt_string)

        if geometry.geom_type == 'Polygon' or geometry.geom_type == 'MultiPolygon':
            return 'area'
        elif geometry.geom_type == 'Point' or geometry.geom_type == 'MultiPoint':
            return 'position'
        elif geometry.geom_type == 'LineString' or geometry.geom_type == 'MultiLineString':
            return 'trajectory'
        else:
            raise Exception(f"Unsupported geometry type: {geometry.geom_type}")

    def _submit_url(self, request: BaseRequest) -> str:
        """Constructs the URL for the request that is used to submit a new Harmony Job."""
        if isinstance(request, CapabilitiesRequest):
            return (f'{self.config.root_url}/capabilities')
        elif request.is_edr_request():
            return (
                f'{self.config.root_url}'
                f'/ogc-api-edr/1.1.0/collections'
                f'/{request.collection.id}'
                f'/{self._wkt_to_edr_route(request.spatial.wkt)}'
            )
        else:
            return (
                f'{self.config.root_url}'
                f'/{request.collection.id}'
                f'/ogc-api-coverages/1.0.0/collections/parameter_vars/coverage/rangeset'
            )

    def _status_url(self, job_id: str, link_type: LinkType = LinkType.https) -> str:
        """Constructs the URL for the Job that is used to get its status."""
        return f'{self.config.root_url}/jobs/{job_id}?linktype={link_type.value}'

    def _pause_url(self, job_id: str, link_type: LinkType = LinkType.https) -> str:
        """Constructs the URL for the Job that is used to pause it."""
        return f'{self.config.root_url}/jobs/{job_id}/pause?linktype={link_type.value}'

    def _resume_url(self, job_id: str, link_type: LinkType = LinkType.https) -> str:
        """Constructs the URL for the Job that is used to resume it."""
        return f'{self.config.root_url}/jobs/{job_id}/resume?linktype={link_type.value}'

    def _cloud_access_url(self) -> str:
        return f'{self.config.root_url}/cloud-access'

    def _params(self, request: BaseRequest) -> dict:
        """Creates a dictionary of request query parameters from the given request."""
        params = {}
        skipped_params = ['shapefile']
        if not isinstance(request, CapabilitiesRequest):
            if request.is_edr_request():
                params['forceAsync'] = True
                if request.spatial:
                    params['coords'] = request.spatial.wkt
                if request.temporal:
                    params['datetime'] = temporal_to_edr_datetime(request.temporal)

                subset = self._dimension_subset_params(request)
                if len(subset) > 0:
                    params['subset'] = subset
            else:
                params['forceAsync'] = 'true'
                subset = self._spatial_subset_params(request) + \
                    self._temporal_subset_params(request) + \
                    self._dimension_subset_params(request)

                if len(subset) > 0:
                    params['subset'] = subset
            if (os.getenv('EXCLUDE_DEFAULT_LABEL') != 'true'):
                labels = request.labels or []
                labels.append(DEFAULT_JOB_LABEL)
                params['label'] = labels
                skipped_params.append('label')

        query_params = [pv for pv in request.parameter_values() if pv[0] not in skipped_params]
        for p, val in query_params:
            if isinstance(val, str):
                params[p] = val
            elif isinstance(val, bool):
                params[p] = str(val).lower()
            elif isinstance(val, list) and not isinstance(val[0], str):
                params[p] = ','.join([str(v) for v in val])
            else:
                params[p] = val

        return params

    def _headers(self) -> dict:
        """
        Create (if needed) and return a dictionary of headers.
        Code partially adapted from:
            https://github.com/requests/toolbelt/blob/master/requests_toolbelt/utils/user_agent.py
        """
        if 'headers' not in self.__dict__:
            session = self._session()
            existing_user_agent_header = session.headers.get('User-Agent')
            if existing_user_agent_header:
                user_agent_content = set([existing_user_agent_header])
            else:
                user_agent_content = set([])

            # Get harmony package info
            user_agent_content.add(f'harmony-py/{harmony_version}')

            # Get platform info
            try:
                p_system = platform.system()
                p_release = platform.release()
                user_agent_content.add(f'{p_system}/{p_release}')
            except Exception as e:
                print("Following exception was caught "
                      "when building user-agent headers for harmony-py:")
                print(e)

            # Get implementation info
            try:
                implementation = platform.python_implementation()
                implementation_version = platform.python_version()
                user_agent_content.add(f'{implementation}/{implementation_version}')
            except Exception as e:
                print("Following exception was caught "
                      "when building user-agent headers for harmony-py:")
                print(e)

            # Build headers
            if user_agent_content:
                self.headers = {'User-Agent': ' '.join(user_agent_content)}
            else:
                self.headers = {}

        return self.headers

    def _spatial_subset_params(self, request: BaseRequest) -> list:
        """Creates a dictionary of spatial subset query parameters."""
        if request.spatial:
            lon_left, lat_lower, lon_right, lat_upper = request.spatial
            return [f'lat({lat_lower}:{lat_upper})', f'lon({lon_left}:{lon_right})']
        else:
            return []

    def _temporal_subset_params(self, request: BaseRequest) -> list:
        """Creates a dictionary of temporal subset query parameters."""
        if request.temporal:
            t = request.temporal
            start = t['start'].isoformat() if 'start' in t else None
            stop = t['stop'].isoformat() if 'stop' in t else None
            start_quoted = f'"{start}"' if start else '*'
            stop_quoted = f'"{stop}"' if stop else '*'
            return [f'time({start_quoted}:{stop_quoted})']
        else:
            return []

    def _dimension_subset_params(self, request: BaseRequest) -> list:
        """Creates a list of dimension subset query parameters."""
        if request.dimensions and len(request.dimensions) > 0:
            dimensions = []
            for dim in request.dimensions:
                dim_min = dim.min if dim.min is not None else '*'
                dim_max = dim.max if dim.max is not None else '*'
                dim_query_param = f'{dim.name}({dim_min}:{dim_max})'
                dimensions.append(dim_query_param)
            return dimensions
        else:
            return []

    @contextmanager
    def _files(self, request) -> ContextManager[Mapping[str, Any]]:
        """Creates a dictionary of multipart file POST parameters from the given request."""
        file_param_names = ['shapefile']
        file_params = dict([pv for pv in request.parameter_values() if pv[0] in file_param_names])

        result = {}
        files = []
        try:
            shapefile_param = file_params.get('shapefile', None)
            if shapefile_param:
                shapefile_ext = shapefile_param.split('.').pop().lower()
                mime = _shapefile_exts_to_mimes[shapefile_ext]
                shapefile = open(shapefile_param, 'rb')
                files.append(shapefile)
                result['shapefile'] = ('shapefile', shapefile, mime)

            yield result
        finally:
            for f in files:
                f.close()

    def _params_dict_to_files(self, params: Mapping[str, Any]) -> List[Tuple[None, str, None]]:
        """Returns the given parameter mapping as a list of tuples suitable for multipart POST
        Args:
            params: A dictionary of parameter mappings as returned by self._params(request)

        Returns:
            A list of tuples suitable for passing to a requests multipart upload corresponding
            to the provided parameters
        """
        result = []
        for key, values in params.items():
            if key == 'granuleId' and isinstance(values, list):
                # Include all granuleId values in a single file boundary as a comma separated
                # list to avoid creating too many file boundaries
                concatenated_values = ','.join(map(str, values))
                result.append((key, (None, concatenated_values, None)))
            else:
                if not isinstance(values, list):
                    values = [values]
                result += [(key, (None, str(value), None)) for value in values]
        return result

    def _get_prepared_request(
            self, request: BaseRequest, for_browser=False) -> requests.models.PreparedRequest:
        """Returns a :requests.models.PreparedRequest: object for the given harmony Request

        Args:
            request: The Harmony Request to prepare
            for_browser: if True only the url with query params will be returned

        Returns:
            A PreparedRequest

        """
        session = self._session()
        params = self._params(request)
        headers = self._headers()

        method = self._http_method(request)
        with self._files(request) as files:
            if (files or method == 'POST') and not for_browser:
                # Ideally this should just be files=files, params=params but Harmony
                # cannot accept both files and query params now.  (HARMONY-290)
                # Inflate params to a list of tuples that can be passed as multipart
                # form-data.  This must be done this way due to e.g. "subset" having
                # multiple values

                # Note: harmony only supports multipart/form-data which is why we use
                # the workaround with files rather than `data=params` even when there
                # is no shapefile to send

                if request.is_edr_request():
                    r = requests.models.Request('POST',
                                                self._submit_url(request),
                                                json=params,
                                                headers=headers)
                else:
                    param_items = self._params_dict_to_files(params)
                    file_items = [(k, v) for k, v in files.items()]
                    all_files = param_items + file_items

                    r = requests.models.Request('POST',
                                                self._submit_url(request),
                                                files=all_files,
                                                headers=headers)
            else:
                if files:
                    raise Exception("Cannot include shapefile as URL query parameter")

                r = requests.models.Request('GET',
                                            self._submit_url(request),
                                            params=params,
                                            headers=headers)

            prepped_request = session.prepare_request(r)
            if for_browser:
                prepped_request.headers = None

        return prepped_request

    def _handle_error_response(self, response: Response):
        """Raises the appropriate exception based on the response
        received from Harmony. Tries to pull out an error message
        from a Harmony JSON response when possible.

        Args:
            response: The Response from Harmony

        Raises:
            Exception with a Harmony error message or a more generic
            HTTPError
        """
        if 'application/json' in response.headers.get('Content-Type', ''):
            exception_message = None
            try:
                response_json = response.json()
                if hasattr(response_json, 'get'):
                    exception_message = response_json.get('description')
                    if not exception_message:
                        exception_message = response_json.get('error')
            except JSONDecodeError:
                pass
            if exception_message:
                raise Exception(response.reason, exception_message)
        response.raise_for_status()

    def request_as_curl(self, request: BaseRequest) -> str:
        """Returns a curl command representation of the given request.
        **Note** Authorization headers will be masked to reduce risk of
        accidental exposure. Also, cookies containing the string 'token'
        will be removed from the curl command.

        Args:
            request: The Request to build a curl command for

        Returns:
            An equivalent curl command as based on this client and request.
        """
        prepped_request = self._get_prepared_request(request)
        if 'Authorization' in prepped_request.headers:
            prepped_request.headers['Authorization'] = '*****'
        if 'Cookie' in prepped_request.headers and 'token' in prepped_request.headers['Cookie']:
            cooks = self._session().cookies.get_dict()
            del prepped_request.headers['Cookie']
            cooks['token'] = '*****'
            prepped_request.prepare_cookies(cooks)
        return curlify.to_curl(prepped_request)

    def request_as_url(self, request: BaseRequest) -> str:
        """Returns a URL string representation of the given request.
        **Note** Headers and cookies are not included, just the URL.
        Shapefiles are not supported.

        Args:
            request: The Request to build the URL string for

        Returns:
            A URL string that can be pasted into a browser.
        :raises
            Exception: if a shapefile is included in the request.
        """
        return self._get_prepared_request(request, for_browser=True).url

    def submit(self, request: BaseRequest) -> any:
        """Submits a request to Harmony and returns the Harmony Job ID.

        Args:
            request: The Request to submit to Harmony (will be validated before sending)

        Returns:
            The Harmony Job ID for request done through async jobs
            The JSON response for direct download request
            The capabilities response for capabilities request
        """
        if not request.is_valid():
            msgs = ', '.join(request.error_messages())
            raise Exception(f"Cannot submit the request due to the following errors: [{msgs}]")

        session = self._session()

        response = session.send(self._get_prepared_request(request))

        if response.ok:
            if isinstance(request, CapabilitiesRequest):
                return response.json()
            elif response.json()['status'] == 'successful':
                return response.json()
            else:
                return response.json()['jobID']
        else:
            self._handle_error_response(response)

    def status(self, job_id: str) -> dict:
        """Retrieve a submitted job's metadata from Harmony.

        Args:
            job_id: UUID string for the job you wish to interrogate.

        Returns:
            A dict of metadata.

        Raises:
            Exception: This can happen if an invalid job_id is provided or Harmony services
              can't be reached.
        """
        session = self._session()
        response = session.get(self._status_url(job_id))
        if response.ok:
            fields = [
                'status', 'message', 'progress', 'createdAt', 'updatedAt', 'dataExpiration',
                'request', 'errors', 'numInputGranules'
            ]
            status_subset = {k: v for k, v in response.json().items() if k in fields}
            created_at_dt = dateutil.parser.parse(status_subset['createdAt'])
            updated_at_dt = dateutil.parser.parse(status_subset['updatedAt'])

            status_json = {
                'status': status_subset['status'],
                'message': status_subset['message']
                .replace(' The job may be resumed using the provided link.', ''),
                'progress': status_subset['progress'],
                'created_at': created_at_dt,
                'updated_at': updated_at_dt,
                'created_at_local': created_at_dt.replace(microsecond=0).astimezone().isoformat(),
                'updated_at_local': updated_at_dt.replace(microsecond=0).astimezone().isoformat(),
                'request': status_subset['request'],
                'num_input_granules': int(status_subset['numInputGranules']),
            }
            if 'dataExpiration' in status_subset:
                data_expiration_dt = dateutil.parser.parse(status_subset['dataExpiration'])
                data_expiration_local = data_expiration_dt.replace(
                    microsecond=0).astimezone().isoformat()
                status_json['data_expiration'] = data_expiration_dt
                status_json['data_expiration_local'] = data_expiration_local
            if 'errors' in status_subset:
                status_json['errors'] = status_subset['errors']
            return status_json
        else:
            self._handle_error_response(response)

    def pause(self, job_id: str):
        """Pause a job.

        Args:
            job_id: UUID string for the job you wish to pause.
        Raises:
            Exception: This can happen if an invalid job_id is provided or Harmony services
              can't be reached or the job cannot be paused (usually because it is already
              in a terminal state).
        """
        session = self._session()
        response = session.get(self._pause_url(job_id))
        if not response.ok:
            if response.status_code == 409:
                # 409 means we could not pause - the json will have a reason
                message = response.json().get('description')
                raise Exception(response.reason, message)
            else:
                response.raise_for_status()

    def resume(self, job_id: str):
        """Resume a job.

        Args:
            job_id: UUID string for the job you wish to resume.
        Raises:
            Exception: This can happen if an invalid job_id is provided or Harmony services
              can't be reached or the job cannot be resumed (usually because it is already
              in a terminal state).
        """
        session = self._session()
        response = session.get(self._resume_url(job_id))
        if response.status_code == 409:
            # 409 means we could not resume - the json will have a reason
            message = response.json().get('description')
            raise Exception(response.reason, message)
        else:
            response.raise_for_status()

    def progress(self, job_id: str) -> Tuple[int, str, str]:
        """Retrieve a submitted job's completion status in percent.

        Args:
            job_id: UUID string for the job you wish to interrogate.

        Returns:
            A tuple of: The job's processing progress as a percentage, the job's processing state,
            and the job's status message

        Raises:
            Exception: This can happen if an invalid job_id is provided or Harmony services
              can't be reached.
        """
        session = self._session()
        response = session.get(self._status_url(job_id))
        if response.ok:
            json = response.json()
            return int(json['progress']), json['status'], json['message']
        else:
            self._handle_error_response(response)

    def wait_for_processing(self, job_id: str, show_progress: bool = False) -> None:
        """Retrieve a submitted job's completion status in percent.

        Args:
            job_id: UUID string for the job you wish to interrogate.

        Returns:
            The job's processing progress as a percentage.

        :raises
            Exception: This can happen if an invalid job_id is provided or Harmony services
            can't be reached.
        """
        # How often to refresh the screen for progress updates and animating spinners.
        ui_update_interval = 0.33  # in seconds
        running_w_errors_logged = False

        intervals = round(self.check_interval / ui_update_interval)
        if show_progress:
            with progressbar.ProgressBar(max_value=100, widgets=progressbar_widgets) as bar:
                progress = 0
                while progress < 100:
                    progress, status, message = self.progress(job_id)
                    if status == 'failed':
                        raise ProcessingFailedException(job_id, message)
                    if status == 'canceled':
                        print('Job has been canceled.')
                        break
                    if status == 'paused':
                        print('\nJob has been paused. Call `resume()` to resume.', file=sys.stderr)
                        break
                    if (not running_w_errors_logged and status == 'running_with_errors'):
                        print('\nJob is running with errors.', file=sys.stderr)
                        running_w_errors_logged = True

                    # This gets around an issue with progressbar. If we update() with 0, the
                    # output shows up as "N/A". If we update with, e.g. 0.1, it rounds down or
                    # truncates to 0 but, importantly, actually displays that.
                    if progress == 0:
                        progress = 0.1

                    for _ in range(intervals):
                        bar.update(progress)  # causes spinner to rotate even when no data change
                        sys.stdout.flush()  # ensures correct behavior in Jupyter notebooks
                        if progress >= 100:
                            break
                        else:
                            time.sleep(ui_update_interval)
        else:
            progress = 0
            while progress < 100:
                progress, status, message = self.progress(job_id)
                if status == 'failed':
                    raise ProcessingFailedException(job_id, message)
                if status == 'canceled':
                    break
                if status == 'paused':
                    print('Job has been paused. Call `resume()` to resume.', file=sys.stderr)
                    break
                if (not running_w_errors_logged and status == 'running_with_errors'):
                    print('\nJob is running with errors.', file=sys.stderr)
                    running_w_errors_logged = True
                time.sleep(self.check_interval)

    def result_json(self,
                    job_id: str,
                    show_progress: bool = False,
                    link_type: LinkType = LinkType.https) -> str:
        """Retrieve a job's final json output.

        Harmony jobs' output is built as the job is processed and this method fetches the complete
        and final output.

        Args:
            job_id: UUID string for the job you wish to interrogate.
            show_progress: Whether a progress bar should show via stdout.
            link_type: The type of link to output, s3:// or https://

        Returns:
            The job's complete json output.
        """
        try:
            self.wait_for_processing(job_id, show_progress)
        except ProcessingFailedException:
            pass
        response = self._session().get(self._status_url(job_id, link_type))
        return response.json()

    def _get_json(self, url: str) -> str:
        """Gets and parses the JSON at the given URL

        Args:
            url: The URL to get

        Returns:
            The parsed JSON contents of the given URL
        """
        return self._session().get(url).json()

    def _result_pages(self,
                      job_id: str,
                      show_progress: bool = False,
                      link_type: LinkType = LinkType.https) -> Generator[object, None, None]:
        """Yields each page of results for the provided job ID

        Args:
            job_id: UUID string for the job to be fetched
            show_progress: Whether a progress bar should show via stdout.
            link_type: The type of link to output, s3:// or https://

        Returns:
            A generator for each page of results, loaded on demand
        """
        self.wait_for_processing(job_id, show_progress)
        next_url = self._status_url(job_id, link_type)
        while next_url:
            response = self._get_json(next_url)
            yield response
            links = response.get('links', [])
            next_url = next((x['href'] for x in links if x['rel'] == 'next'), None)

    def result_urls(self,
                    job_id: str,
                    show_progress: bool = False,
                    link_type: LinkType = LinkType.https) -> Generator[str, None, None]:
        """Retrieve the data URLs for a job.

        The URLs include links to all of the jobs data output. Blocks until the Harmony job is
        done processing.

        Args:
            job_id: UUID string for the job you wish to interrogate.
            show_progress: Whether a progress bar should show via stdout.
            link_type: The type of link to output, s3:// or https://

        Returns:
            The job's complete list of data URLs.
        """
        for page in self._result_pages(job_id, show_progress, link_type):
            for link in page.get('links', []):
                if link['rel'] == 'data':
                    yield link['href']

    def _is_staged_result(self, url: str) -> str:
        """Check if the URL indicates that the data is associated with actual
        service outputs (as opposed to a download link for example).

        Args:
            url: The location (URL) of the file to be downloaded

        Returns:
            A boolean indicating whether the data is staged data.
        """
        if 'harmony' not in url:
            return False
        url_parts = url.split('/')
        possible_uuid = url_parts[-3]
        possible_item_id = url_parts[-2]
        try:
            uuid_obj = UUID(possible_uuid, version=4)
        except ValueError:
            return False
        if str(uuid_obj) != possible_uuid:
            return False
        if not possible_item_id.isnumeric():
            return False
        return True

    def get_download_filename_from_url(self, url: str) -> str:
        """For a given URL, returns the filename that will be used for download.
        It will include a Harmony generated ID prefix if the data is staged.

        Args:
            url: The location (URL) of the file to be downloaded

        Returns:
            The filename that will be used to name the downloaded file.
        """
        name_result = None
        url_no_query = parse.urlunparse(parse.urlparse(url)._replace(query=""))
        url_parts = url_no_query.split('/')
        original_filename = url_parts[-1]

        is_staged_result = self._is_staged_result(url_no_query)
        if not is_staged_result:
            name_result = original_filename
        else:
            item_id = url_parts[-2]
            name_result = f'{item_id}_{original_filename}'
        return name_result.replace(':', '_')

    def _download_file(self, url: str, directory: str = '', overwrite: bool = False) -> str:
        """Downloads data, saves it to a file, and returns the filename.

        Performance should be close to native with an appropriate chunk size. This can be changed
        via environment variable DOWNLOAD_CHUNK_SIZE.

        Filenames are automatically determined by using the latter portion of the provided URL
        and will be prefixed by the item id generated by Harmony when data was transformed
        from the original.

        Args:
            url: The location (URL) of the file to be downloaded
            directory: Optional. If specified, saves files there. Saves files to the current
            working directory by default.
            overwrite: If True, will overwrite a local file that shares a filename with the
            downloaded file. Defaults to False. If you're seeing malformed data or truncated
            files from incomplete downloads, set overwrite to True.

        Returns:
            The filename and path.
        """
        chunksize = int(self.config.DOWNLOAD_CHUNK_SIZE)
        session = self._session()
        filename = self.get_download_filename_from_url(url)
        new_url = url

        if directory:
            filename = os.path.join(directory, filename)

        verbose = os.getenv('VERBOSE', 'TRUE')
        if not overwrite and os.path.isfile(filename):
            if verbose and verbose.upper() == 'TRUE':
                print(filename)
            return filename
        else:
            data_dict = None
            parse_result = parse.urlparse(url)
            is_opendap = parse_result.netloc.startswith('opendap')
            method = 'post' if is_opendap else 'get'
            if is_opendap:  # remove the query params from the URL and convert to dict
                new_url = parse.urlunparse(parse_result._replace(query=""))
                data_dict = dict(parse.parse_qsl(parse.urlsplit(url).query))
            headers = {
                "Accept-Encoding": "identity"
            }
            with getattr(session, method)(
                    new_url, data=data_dict, stream=True, headers=headers) as r:
                with open(filename, 'wb') as f:
                    shutil.copyfileobj(r.raw, f, length=chunksize)
            if verbose and verbose.upper() == 'TRUE':
                print(filename)
            return filename

    def download(self, url: str, directory: str = '', overwrite: bool = False) -> Future:
        """Downloads data and saves it to a file asynchronously.

        Args:
            url: The location (URL) of the file to be downloaded
            directory: Optional. If specified, saves files there. Saves files to the current
            working directory by default.
            overwrite: If True, will overwrite a local file that shares a filename with the
            downloaded file. Defaults to False. If you're seeing malformed data or truncated
            files from incomplete downloads, set overwrite to True.

        Returns:
            A Future that resolves to the full path to the file.
        """
        if url.endswith('zarr'):
            raise self.zarr_download_exception
        future = self.executor.submit(self._download_file, url, directory, overwrite)
        return future

    def download_all(self,
                     job_id_or_result_json: Union[str, dict],
                     directory: str = '',
                     overwrite: bool = False) -> Generator[Future, None, None]:
        """Using a job_id, fetches all the data files from a finished job.

        After this method is able to contact Harmony and query a finished job, it will
        immediately return with a list of python concurrent.Futures corresponding to each of the
        files to be downloaded. Call the result() method to block until the downloading of that
        file is complete. When finished, the Future will return the filename.

        Files are downloaded by an executor backed by a thread pool. Number of threads in the
        thread pool can be specified with the environment variable NUM_REQUESTS_WORKERS.

        Performance should be close to native with an appropriate chunk size. This can be changed
        via environment variable ``DOWNLOAD_CHUNK_SIZE``.

        Filenames are automatically determined by using the latter portion of the provided URL.

        Will wait for an unfinished job to finish before downloading.

        Args:
            job_id: UUID string for the job you wish to interrogate.
            directory: Optional. If specified, saves files there. Saves files to the current
            working directory by default.
            overwrite: If True, will overwrite a local file that shares a filename with the
            downloaded file. Defaults to False. If you're seeing malformed data or truncated
            files from incomplete downloads, set overwrite to True.

        Returns:
            A list of Futures, each of which will return the filename (with path) for each
            result.
        """
        if isinstance(job_id_or_result_json, str):
            for url in self.result_urls(job_id_or_result_json, show_progress=False) or []:
                if url.endswith('zarr'):
                    raise self.zarr_download_exception
                yield self.executor.submit(self._download_file, url, directory, overwrite)
        else:
            for link in job_id_or_result_json.get('links', []):
                if link['rel'] == 'data':
                    url = link['href']
                    if url.endswith('zarr'):
                        raise self.zarr_download_exception
                    yield self.executor.submit(self._download_file, url, directory, overwrite)

    def iterator(
        self,
        job_id: str,
        directory: str = '',
        overwrite: bool = False
    ) -> Iterator:
        """Create an iterator that will poll for data in the background and download it as
        it is available and requested via `next()`.

        Each iteration returns a dictionary, or `None` when all granules have been iterated.
        The dictionary has the following form:

        .. code-block:: python

            {
                'path': Future
                'bbox': BBox object containing the bounding box for the granule,
                'temporal': {
                    'start': '2020-01-11T14:00:00.000Z',
                    'end': '2020-01-11T15:59:59.000Z'
                }
            }

        The Future resolves to the path to the downloaded file.

        If the job is paused and all processed granules have already been returned in
        the iteration, the status returned will be GranuleStatus.PAUSED until the job
        is resumed.

        If the job fails during iteration then calls to `next` will raise an exception.
        Note that this is not true if the job completed with errors, in which case specific
        granules may return errors, but no exception is raised. This allows the caller
        to retrieve any granules that were successfully processed.

        Note: if a job gets stuck in the 'running' state, this iterator will happily wait
        forever re-checking the status page periodically.

        Args:
            job_id: UUID string for the job you wish to interrogate.
            directory: Optional. If specified, saves files there. Saves files to the current
            working directory by default.
            overwrite: If True, will overwrite a local file that shares a filename with the
            downloaded file. Defaults to False. If you're seeing malformed data or truncated
            files from incomplete downloads, set overwrite to True.

        Returns:
            An Iterator that can be used to iterate over the granule results from a job
        """
        GET_JSON_RETRY_LIMIT = int(os.getenv('GET_JSON_RETRY_LIMIT', 3))
        GET_JSON_RETRY_SLEEP = float(os.getenv('GET_JSON_RETRY_SLEEP', 1.0))
        next_url = self._status_url(job_id)

        # index used to keep track of where we are in the data links if the page gets reloaded
        # so we don't pull the same granule more than once
        # NOTE: this relies on the link order being preserved when the harmony job status page
        # is reloaded and new links are added.
        current_page_granule_count = 0

        while next_url:
            self_url = next_url
            last_pull_time = datetime.now()
            response = None
            get_json_try_count = 0
            # work around for occasional failures in the status page
            while not response:
                try:
                    response = self._get_json(next_url)
                except BaseException:
                    response = None
                    get_json_try_count += 1
                    if get_json_try_count < GET_JSON_RETRY_LIMIT:
                        time.sleep(GET_JSON_RETRY_SLEEP)
                    else:
                        raise Exception('Failed to get or parse job status page')

            next_url = None
            status = response.get('status')
            if status == 'failed':
                raise Exception(response.get('message'))

            links = response.get('links', [])
            link_index = 0
            for link in links:
                if link['rel'] == 'data':
                    link_index += 1
                    if link_index > current_page_granule_count:
                        current_page_granule_count = link_index
                        future = self.download(link['href'], directory, overwrite)
                        bbox = link['bbox']
                        temporal = link['temporal']
                        yield {
                            'path': future,
                            'bbox': BBox(bbox[0], bbox[1], bbox[2], bbox[3]),
                            'temporal': temporal
                        }
                elif link['rel'] == 'next':
                    next_url = link['href']

            if not next_url:
                # no 'next' link means either we are done or we need to reload this page to
                # get more results
                if status in {'successful', 'paused', 'canceled', 'complete_with_errors'}:
                    # we are done ('failed' case is already handled above by raising an exception)
                    if status == 'paused':
                        print('Job is paused. Resume to continue processing.')
                    return None
                else:
                    # reload the page to see if status has changed and/or more granules are
                    # available
                    next_url = self_url
                    # might need to sleep for a bit to avoid overwhelming Harmony
                    delta_time_since_last_pull = datetime.now() - last_pull_time
                    seconds_since_last_pull = delta_time_since_last_pull.total_seconds()
                    if seconds_since_last_pull < self.check_interval:
                        time.sleep(self.check_interval - seconds_since_last_pull)
            else:
                # reset the index for the links since we are going to load a new page
                link_index = 0
                current_page_granule_count = 0

    def stac_catalog_url(self,
                         job_id: str,
                         show_progress: bool = False,
                         link_type: LinkType = LinkType.https) -> str:
        """Extract the STAC catalog URL from job results.

        Blocks until the Harmony job is done processing.

        Args:
            job_id: UUID string for the job you wish to interrogate.
            show_progress: Whether a progress bar should show via stdout.
            link_type: The type of link to output, s3:// or https://

        Returns:
            A STAC catalog URL.

        :raises
            Exception: This can happen if an invalid job_id is provided or Harmony services
            can't be reached.
        """
        data = self.result_json(job_id, show_progress, link_type)

        for link in data.get('links', []):
            if link['rel'] == 'stac-catalog-json':
                return f"{link['href']}?linktype={link_type.value}"

        return None

    def read_text(self, url: str) -> str:
        """Uses the harmony-py Client session to fetch a URL.

        Args:
            url: A URL, such as one from stac_catalog_url().

        Returns:
            The response text.

        :raises Exception: Can occur on malformed or unreachable URLs.
        """
        response = self._session().get(url)
        if not response.ok:
            response.raise_for_status()
        return response.text

    def aws_credentials(self) -> dict:
        """Retrieve temporary AWS credentials for retrieving data in S3.

        Returns:
            A python dict containing ``aws_access_key_id``, ``aws_secret_access_key``, and
            ``aws_session_token``.

        :raises Exception: Can raise when e.g. server is unreachable.
        """
        response = self._session().get(self._cloud_access_url())
        if not response.ok:
            response.raise_for_status()
        cloud_access = response.json()
        creds = {
            'aws_access_key_id': cloud_access['AccessKeyId'],
            'aws_secret_access_key': cloud_access['SecretAccessKey'],
            'aws_session_token': cloud_access['SessionToken'],
        }
        return creds
