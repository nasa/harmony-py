from os.path import basename
from urllib.parse import urlparse


def s3_components(url: str) -> tuple:
    """Returns a tuple with the S3 bucket, key, and file names parsed from the S3 URL.

    Note: the url should be a valid S3 url. For example ::

        s3://bucket-name/full/path/data.nc

    In this case, the function will return the tuple:

        ('bucket-name', 'full/path', 'data.nc')

    This tuple may be used to more easily download data using the boto3 API.

    Args:
        url: a valid S3 URL

    Returns:
        A tuple containing the strings (bucket, object, filename).
    """
    parsed = urlparse(url)
    return (parsed.netloc, parsed.path.lstrip('/'), basename(parsed.path))
