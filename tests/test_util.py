import pytest

from harmony.util import s3_components


@pytest.mark.parametrize('bucket, path, fn', [
    ('harmony-uat-staging', 'public/harmony/gdal/aed38eeb-f01a-41bb-a790-affbb2ab2bd6',
     '2020_01_01_7f00ff_global_blue_var_regridded_subsetted.nc.tif'),
    ('foo', 'bar', 'xyzzy.txt'),
    ('foo', '', 'xyzzy.nc')
])
def test_s3_url_parts(bucket, path, fn):
    key = f'{path}/{fn}' if path else fn
    url = f's3://{bucket}/{key}'

    assert (bucket, key, fn) == s3_components(url)
