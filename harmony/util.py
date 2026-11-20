import csv
from os.path import basename
from typing import Any, List, Optional
from urllib.parse import urlparse

import requests
from requests import Response


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


def get_json_from_response(response: Response) -> Any:
    """Parses and returns the JSON body from a Harmony response.

    Args:
        response: The Response object returned by a Harmony request.

    Returns:
        The parsed JSON body as a Python object.

    :raises
        Exception: If the response body is not valid JSON. Provides a more specific
        message if the response appears to be an Earthdata Login authentication page.
    """
    try:
        return response.json()
    except requests.exceptions.JSONDecodeError as e:
        if 'Earthdata Login' in response.text:
            raise Exception(
                'Harmony returned a non-JSON response. This may indicate an '
                'authentication failure. Try using a token for authentication when '
                'creating your Client or check that your .netrc file contains valid '
                'credentials for the Earthdata Login host (e.g. '
                'urs.earthdata.nasa.gov or uat.urs.earthdata.nasa.gov).\n'
                f'Raw response ({response.status_code}): {response.text[:200]}'
            ) from e
        else:
            raise Exception(f'Harmony returned a non-JSON response: {response.text[:200]}') from e


def combine_csv_files(
    input_filenames: List[str],
    output_filename: str,
    id_column: Optional[str] = None,
    ids: Optional[List[str]] = None,
) -> None:
    """Combines CSV files into a single CSV file with one header row.

    The input files don't need to have identical columns. The output's columns are the
    union of the input files' columns, in the order they're first seen, and a row from a
    file without a given column has an empty value for it. Rows are written in the order
    of ``input_filenames``, and lines end with ``\\n``.

    Args:
        input_filenames: The CSV files to combine. Each must start with a header row.
        output_filename: The file to write the combined CSV to. Overwritten if it exists.
        id_column: Optional. The name of a column to add as the output's first column,
            identifying which input each row came from. Requires ``ids``.
        ids: Optional. One value per input file, in the same order as ``input_filenames``,
            to put in ``id_column`` for that file's rows.

    :raises
        ValueError: If only one of ``id_column`` and ``ids`` is given, ``ids`` doesn't have
        one value per input file, or an input file already has a column named ``id_column``.
    """
    if (id_column is None) != (ids is None):
        raise ValueError('id_column and ids must be given together.')
    if ids is not None and len(ids) != len(input_filenames):
        raise ValueError('ids must have one value per input file.')

    fieldnames = {}
    for filename in input_filenames:
        with open(filename, newline='', encoding='utf-8') as input_file:
            header = next(csv.reader(input_file), [])
        if id_column is not None and id_column in header:
            raise ValueError(f'{filename} already has a column named {id_column}.')
        fieldnames.update(dict.fromkeys(header))

    with open(output_filename, 'w', newline='', encoding='utf-8') as output_file:
        if not fieldnames:
            return
        if id_column is not None:
            fieldnames = {id_column: None, **fieldnames}
        writer = csv.DictWriter(output_file, fieldnames=list(fieldnames), lineterminator='\n')
        writer.writeheader()
        for index, filename in enumerate(input_filenames):
            with open(filename, newline='', encoding='utf-8') as input_file:
                for row in csv.DictReader(input_file):
                    if id_column is not None:
                        row[id_column] = ids[index]
                    writer.writerow(row)
