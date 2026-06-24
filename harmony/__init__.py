from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("harmony-py")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0.0.0+unknown"

from harmony.config import Environment
from harmony.request import BBox, WKT, Collection, LinkType, Dimension, Request, \
    CapabilitiesRequest, AddLabelsRequest, DeleteLabelsRequest, JobsRequest
from harmony.client import Client
from harmony.util import s3_components
