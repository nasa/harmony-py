from datetime import datetime
from enum import Enum
import os
from shapely.lib import ShapelyError
from shapely.wkt import loads
from typing import Any, ContextManager, IO, Iterator, List, Mapping, NamedTuple, Optional, \
    Tuple, Generator, Union


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


class HttpMethod(Enum):
    """Enumeration of HTTP methods used in Harmony requests.

    This enum defines the standard HTTP methods that can be used when making requests
    to the Harmony API.
    """
    GET = "GET"
    PUT = "PUT"
    POST = "POST"
    DELETE = "DELETE"


class BaseRequest:
    """A Harmony base request for all client requests. It is the base class of all harmony
    requests.

    Args:
        collection: The CMR collection that should be queried

    Returns:
        A Harmony Request instance
    """

    def __init__(self,
                 *,
                 http_method: HttpMethod = HttpMethod.GET):
        self.http_method = http_method

    def error_messages(self) -> List[str]:
        """A list of error messages, if any, for the request.
        Validation of request parameters should go here.
        Returns the list of validation error messages back if any"""
        return []

    def is_valid(self) -> bool:
        """Determines if the request and its parameters are valid."""
        return len(self.error_messages()) == 0

    def parameter_values(self) -> List[Tuple[str, Any]]:
        """Returns tuples of each query parameter that has been set and its value."""
        pvs = [(param, getattr(self, variable))
               for variable, param in self.variable_name_to_query_param.items()]
        return [(p, v) for p, v in pvs if v is not None]


class OgcBaseRequest(BaseRequest):
    """A Harmony OGC base request with the CMR collection. It is the base class of OGC harmony
    requests.

    Args:
        collection: The CMR collection that should be queried

    Returns:
        A Harmony Request instance
    """

    def __init__(self,
                 *,
                 collection: Collection):
        super().__init__(http_method=HttpMethod.POST)
        self.collection = collection
        self.variable_name_to_query_param = {}


def is_wkt_valid(wkt_string: str) -> bool:
    try:
        # Attempt to load the WKT string
        loads(wkt_string)
        return True
    except (ShapelyError, ValueError) as e:
        # Handle WKT reading errors and invalid WKT strings
        print(f"Invalid WKT: {e}")
        return False


class Request(OgcBaseRequest):
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

        average: the type of averaging to perform

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

        pixel_subset: Whether to perform pixel subset

        service_id: The CMR UMM-S concept ID or service chain name to invoke. Only supported in
          test environments for testing collections not yet associated with a service.

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
                 average: str = None,
                 skip_preview: bool = None,
                 ignore_errors: bool = None,
                 grid: str = None,
                 labels: List[str] = None,
                 pixel_subset: bool = None,
                 service_id: str = None):
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
        self.average = average
        self.skip_preview = skip_preview
        self.ignore_errors = ignore_errors
        self.grid = grid
        self.labels = labels
        self.pixel_subset = pixel_subset
        self.service_id = service_id

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
                'pixel_subset': 'pixelSubset',
                'service_id': 'serviceId',
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
                'average': 'average',
                'skip_preview': 'skipPreview',
                'ignore_errors': 'ignoreErrors',
                'grid': 'grid',
                'extend': 'extend',
                'variables': 'variable',
                'labels': 'label',
                'pixel_subset': 'pixelSubset',
                'service_id': 'serviceId'
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
             'Destination URL must be an S3 location'),
            (self.concatenate is None or isinstance(self.concatenate, bool),
             'concatenate must be a boolean (True or False)'),
            (self.ignore_errors is None or isinstance(self.ignore_errors, bool),
             'ignore_errors must be a boolean (True or False)'),
            (self.skip_preview is None or isinstance(self.skip_preview, bool),
             'skip_preview must be a boolean (True or False)'),
            (self.pixel_subset is None or isinstance(self.pixel_subset, bool),
             'pixel_subset must be a boolean (True or False)')
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
    """A Harmony request to retrieve the capabilities of a CMR collection.

    This request queries the Harmony API for the capabilities of a specified CMR
    (Common Metadata Repository) collection, allowing users to retrieve metadata
    about available processing and data access options.

    Args:
        collection_id (str, optional): The CMR collection ID to query.
        short_name (str, optional): The short name of the CMR collection.
        capabilities_version (str, optional): The version of the collection
            capabilities request API.

    Returns:
        CapabilitiesRequest: An instance of the request configured with
        the provided parameters.
    """

    def __init__(self,
                 **request_params
                 ):

        super().__init__()
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


class AddLabelsRequest(BaseRequest):
    """A Harmony request to add labels on jobs.

    Args:
        labels (List[str]): A list of labels to be added.
        job_ids (List[str]): A list of job IDs to which the labels apply.

    Returns:
        AddLabelsRequest: An instance of the request configured with the provided parameters.
    """

    def __init__(self,
                 *,
                 labels: List[str],
                 job_ids: List[str]
                 ):
        super().__init__(http_method=HttpMethod.PUT)
        self.labels = labels
        self.job_ids = job_ids

        self.variable_name_to_query_param = {
            'labels': 'label',
            'job_ids': 'jobID',
        }


class DeleteLabelsRequest(BaseRequest):
    """A Harmony request to delete labels from jobs.

    Args:
        labels (List[str]): A list of labels to be removed.
        job_ids (List[str]): A list of job IDs to which the labels apply.

    Returns:
        DeleteLabelsRequest: An instance of the request configured with the provided parameters.
    """

    def __init__(self,
                 *,
                 labels: List[str],
                 job_ids: List[str]
                 ):
        super().__init__(http_method=HttpMethod.DELETE)
        self.labels = labels
        self.job_ids = job_ids

        self.variable_name_to_query_param = {
            'labels': 'label',
            'job_ids': 'jobID',
        }


class JobsRequest(BaseRequest):
    """A Harmony request to list or search for jobs.

    Args:
        page (int): The current page number.
        limit (int): The number of jobs in each page.
        labels (List[str]): A list of labels to search jobs with.

    Returns:
        JobsRequest: An instance of the jobs request configured with the provided parameters.
    """

    def __init__(self,
                 *,
                 page: int = None,
                 limit: int = None,
                 labels: List[str] = None,
                 ):
        super().__init__()
        self.page = page
        self.limit = limit
        self.labels = labels

        self.variable_name_to_query_param = {
            'page': 'page',
            'limit': 'limit',
            'labels': 'label',
        }


class LinkType(Enum):
    """The type of URL to provide when returning links to data."""
    s3 = 's3'
    http = 'http'
    https = 'https'
