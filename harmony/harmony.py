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
import os
import shutil
import sys
import time
import platform
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from typing import Any, ContextManager, IO, List, Mapping, NamedTuple, Optional, Tuple

import dateutil.parser
import progressbar

from harmony.auth import create_session, validate_auth
from harmony.config import Config, Environment

progressbar_widgets = [
    ' [ Processing: ', progressbar.Percentage(), ' ] ',
    progressbar.Bar(),
    ' [', progressbar.RotatingMarker(), ']',
]


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


_shapefile_exts_to_mimes = {
    'json': 'application/geo+json',
    'geojson': 'application/geo+json',
    'kml': 'application/vnd.google-earth.kml+xml',
    'shz': 'application/shapefile+zip',
    'zip': 'application/shapefile+zip',
}
_valid_shapefile_exts = ', '.join((_shapefile_exts_to_mimes.keys()))


class Request:
    """A Harmony request with the CMR collection and various parameters expressing
    how the data is to be transformed.

    Args:
        collection: The CMR collection that should be queried

        spatial: Bounding box spatial constraints on the data

        temporal: Date/time constraints on the data provided as a dict mapping "start" and "stop"
          keys to corresponding start/stop datetime.datetime objects

        crs: reproject the output coverage to the given CRS.  Recognizes CRS types that can be
          inferred by gdal, including EPSG codes, Proj4 strings, and OGC URLs
          (http://www.opengis.net/def/crs/...)

        interpolation: specify the interpolation method used during reprojection and scaling

        scale_extent: scale the resulting coverage either among one axis to a given extent

        scale_size: scale the resulting coverage either among one axis to a given size

        shape: a file path to an ESRI Shapefile zip, GeoJSON file, or KML file to use for
          spatial subsetting.  Note: not all collections support shapefile subsetting

        granule_id: The CMR Granule ID for the granule which should be retrieved

        width: number of columns to return in the output coverage

        height: number of rows to return in the output coverage

        format: the output mime type to return

        max_results: limits the number of input granules processed in the request

    Returns:
        A Harmony Request instance
    """

    def __init__(self,
                 collection: Collection,
                 *,
                 spatial: BBox = None,
                 temporal: Mapping[str, datetime] = None,
                 crs: str = None,
                 format: str = None,
                 granule_id: List[str] = None,
                 height: int = None,
                 interpolation: str = None,
                 max_results: int = None,
                 scale_extent: List[float] = None,
                 scale_size: List[float] = None,
                 shape: Optional[Tuple[IO, str]] = None,
                 variables: List[str] = ['all'],
                 width: int = None):
        """Creates a new Request instance from all specified criteria.'
        """
        self.collection = collection
        self.spatial = spatial
        self.temporal = temporal
        self.crs = crs
        self.format = format
        self.granule_id = granule_id
        self.height = height
        self.interpolation = interpolation
        self.max_results = max_results
        self.scale_extent = scale_extent
        self.scale_size = scale_size
        self.shape = shape
        self.variables = variables
        self.width = width

        self.variable_name_to_query_param = {
            'crs': 'outputcrs',
            'interpolation': 'interpolation',
            'scale_extent': 'scaleExtent',
            'scale_size': 'scaleSize',
            'shape': 'shapefile',
            'granule_id': 'granuleId',
            'width': 'width',
            'height': 'height',
            'format': 'format',
            'max_results': 'maxResults',
        }

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
        self.shape_validations = [
            (lambda s: os.path.isfile(s), 'The provided shape path is not a file'),
            (lambda s: s.split('.').pop().lower() in _shapefile_exts_to_mimes,
             'The provided shape file is not a recognized type.  Valid file extensions: '
             + f'[{_valid_shapefile_exts}]'),
        ]

    def parameter_values(self) -> List[Tuple[str, Any]]:
        """Returns tuples of each query parameter that has been set and its value."""
        pvs = [(param, getattr(self, variable))
               for variable, param in self.variable_name_to_query_param.items()]
        return [(p, v) for p, v in pvs if v is not None]

    def is_valid(self) -> bool:
        """Determines if the request and its parameters are valid."""
        return len(self.error_messages()) == 0

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

    def error_messages(self) -> List[str]:
        """A list of error messages, if any, for the request."""
        spatial_msgs = []
        temporal_msgs = []
        shape_msgs = self._shape_error_messages(self.shape)
        if self.spatial:
            spatial_msgs = [m for v, m in self.spatial_validations if not v(self.spatial)]
        if self.temporal:
            temporal_msgs = [m for v, m in self.temporal_validations if not v(self.temporal)]

        return spatial_msgs + temporal_msgs + shape_msgs


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

    By default, the Client will validate the provided credentials immediately. This can be
    disabled by passing ``should_validate_auth=False``.
    """

    def __init__(
        self,
        *,
        auth: Optional[Tuple[str, str]] = None,
        should_validate_auth: bool = True,
        env: Environment = Environment.PROD,
    ):
        """Creates a Harmony Client that can be used to interact with Harmony.

        Args:
            auth : A tuple of the format ('edl_username', 'edl_password')
            should_validate_auth: Whether EDL credentials will be validated.
        """
        self.config = Config(env)
        self.session = None
        self.auth = auth

        num_workers = int(self.config.NUM_REQUESTS_WORKERS)
        self.executor = ThreadPoolExecutor(max_workers=num_workers)

        if should_validate_auth:
            validate_auth(self.config, self._session())

    def _session(self):
        """Creates (if needed) and returns the Client's requests Session."""
        if self.session is None:
            self.session = create_session(self.config, self.auth)
        return self.session

    def _submit_url(self, request: Request) -> str:
        """Constructs the URL for the request that is used to submit a new Harmony Job."""
        variables = [v.replace('/', '%2F') for v in request.variables]
        vars = ','.join(variables)
        return (
            f'{self.config.root_url}'
            f'/{request.collection.id}'
            f'/ogc-api-coverages/1.0.0/collections/{vars}/coverage/rangeset'
        )

    def _status_url(self, job_id: str, link_type: LinkType = LinkType.https) -> str:
        """Constructs the URL for the Job that is used to get its status."""
        return f'{self.config.root_url}/jobs/{job_id}?linktype={link_type.value}'

    def _cloud_access_url(self) -> str:
        return f'{self.config.root_url}/cloud-access'

    def _params(self, request: Request) -> dict:
        """Creates a dictionary of request query parameters from the given request."""
        params = {'forceAsync': 'true'}

        subset = self._spatial_subset_params(request) + self._temporal_subset_params(request)
        if len(subset) > 0:
            params['subset'] = subset

        file_param_names = ['shapefile']
        query_params = [pv for pv in request.parameter_values() if pv[0] not in file_param_names]
        for p, val in query_params:
            if type(val) == str:
                params[p] = val
            elif type(val) == bool:
                params[p] = str(val).lower()
            elif type(val) == list and type(val[0]) != str:
                params[p] = ','.join([str(v) for v in val])
            else:
                params[p] = val

        return params

    def _headers(self) -> dict:
        """Create (if needed) and returns a dictionary of headers."""
        if self.headers is None:
            self.headers = {}
        return self.headers

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
            start_quoted = f'"{start}"' if start else '*'
            stop_quoted = f'"{stop}"' if stop else '*'
            return [f'time({start_quoted}:{stop_quoted})']
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

        This method is a temporary need until HARMONY-290 is implemented, since we cannot
        currently pass query parameters to a shapefile POST request.  Because we need to pass
        them as a multipart POST body, we need to inflate them into a list of tuples, one for
        each parameter value to allow us to call requests.post(..., files=params)

        Args:
            params: A dictionary of parameter mappings as returned by self._params(request)

        Returns:
            A list of tuples suitable for passing to a requests multipart upload corresponding
            to the provided parameters
        """
        # TODO: remove / refactor after HARMONY-290 is complete
        result = []
        for key, values in params.items():
            if not isinstance(values, list):
                values = [values]
            result += [(key, (None, str(value), None)) for value in values]
        return result

    def submit(self, request: Request) -> Optional[str]:
        """Submits a request to Harmony and returns the Harmony Job ID.

        Args:
            request: The Request to submit to Harmony (will be validated before sending)

        Returns:
            The Harmony Job ID
        """
        if not request.is_valid():
            msgs = ', '.join(request.error_messages())
            raise Exception(f"Cannot submit the request due to the following errors: [{msgs}]")

        job_id = None
        session = self._session()
        params = self._params(request)

        with self._files(request) as files:
            if files:
                # Ideally this should just be files=files, params=params but Harmony
                # cannot accept both files and query params now.  (HARMONY-290)
                # Inflate params to a list of tuples that can be passed as multipart
                # form-data.  This must be done this way due to e.g. "subset" having
                # multiple values

                param_items = self._params_dict_to_files(params)
                file_items = [(k, v) for k, v in files.items()]
                response = session.post(
                    self._submit_url(request),
                    files=param_items + file_items)
            else:
                response = session.get(self._submit_url(request), params=params)
        if response.ok:
            print(response.json())
            job_id = (response.json())['jobID']
        else:
            response.raise_for_status()

        # Add user-agent headers

        return job_id

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
                'status', 'message', 'progress', 'createdAt', 'updatedAt', 'request',
                'numInputGranules'
            ]
            status_subset = {k: v for k, v in response.json().items() if k in fields}
            return {
                'status': status_subset['status'],
                'message': status_subset['message'],
                'progress': status_subset['progress'],
                'created_at': dateutil.parser.parse(status_subset['createdAt']),
                'updated_at': dateutil.parser.parse(status_subset['updatedAt']),
                'request': status_subset['request'],
                'num_input_granules': int(status_subset['numInputGranules']),
            }
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
            response.raise_for_status()

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
        # How often to poll Harmony for updated information during job processing.
        check_interval = 3.0  # in seconds
        # How often to refresh the screen for progress updates and animating spinners.
        ui_update_interval = 0.33  # in seconds

        intervals = round(check_interval / ui_update_interval)
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
                time.sleep(check_interval)

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

        Returns:
            The job's complete json output.
        """
        try:
            self.wait_for_processing(job_id, show_progress)
        except ProcessingFailedException:
            pass
        response = self._session().get(self._status_url(job_id))
        return response.json()

    def result_urls(self,
                    job_id: str,
                    show_progress: bool = False,
                    link_type: LinkType = LinkType.https) -> List:
        """Retrieve the data URLs for a job.

        The URLs include links to all of the jobs data output. Blocks until the Harmony job is
        done processing.

        Args:
            job_id: UUID string for the job you wish to interrogate.
            show_progress: Whether a progress bar should show via stdout.

        Returns:
            The job's complete list of data URLs.
        """
        data = self.result_json(job_id, show_progress, link_type)
        urls = [x['href'] for x in data.get('links', []) if x['rel'] == 'data']
        return urls

    def _download_file(self, url: str, directory: str = '', overwrite: bool = False) -> str:
        chunksize = int(self.config.DOWNLOAD_CHUNK_SIZE)
        session = self._session()
        filename = url.split('/')[-1]

        if directory:
            filename = os.path.join(directory, filename)

        if not overwrite and os.path.isfile(filename):
            return filename
        else:
            with session.get(url, stream=True) as r:
                with open(filename, 'wb') as f:
                    shutil.copyfileobj(r.raw, f, length=chunksize)
            return filename

    def download(self, url: str, directory: str = '', overwrite: bool = False) -> Future:
        """Downloads data, saves it to a file, and returns the filename.

        Performance should be close to native with an appropriate chunk size. This can be changed
        via environment variable DOWNLOAD_CHUNK_SIZE.

        Filenames are automatically determined by using the latter portion of the provided URL.

        Args:
            job_id: UUID string for the job you wish to interrogate.
            directory: Optional. If specified, saves files there. Saves files to the current
            working directory by default.
            overwrite: If True, will overwrite a local file that shares a filename with the
            downloaded file. Defaults to False. If you're seeing malformed data or truncated
            files from incomplete downloads, set overwrite to True.

        Returns:
            The filename and path.
        """
        future = self.executor.submit(self._download_file, url, directory, overwrite)
        return future

    def download_all(self,
                     job_id: str,
                     directory: str = '',
                     overwrite: bool = False) -> List[Future]:
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
        urls = self.result_urls(job_id, show_progress=False) or []
        return [
            self.executor.submit(self._download_file, url, directory, overwrite) for url in urls
        ]

    def stac_catalog_url(self,
                         job_id: str,
                         show_progress: bool = False,
                         link_type: LinkType = LinkType.https) -> str:
        """Extract the STAC catalog URL from job results.

        Blocks until the Harmony job is done processing.

        Args:
            job_id: UUID string for the job you wish to interrogate.
            show_progress: Whether a progress bar should show via stdout.

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
