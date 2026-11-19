import pytest

from harmony.util import combine_csv_files, s3_components


@pytest.mark.parametrize(
    'bucket, path, fn',
    [
        (
            'harmony-uat-staging',
            'public/harmony/gdal/aed38eeb-f01a-41bb-a790-affbb2ab2bd6',
            '2020_01_01_7f00ff_global_blue_var_regridded_subsetted.nc.tif',
        ),
        ('foo', 'bar', 'xyzzy.txt'),
        ('foo', '', 'xyzzy.nc'),
    ],
)
def test_s3_url_parts(bucket, path, fn):
    key = f'{path}/{fn}' if path else fn
    url = f's3://{bucket}/{key}'

    assert (bucket, key, fn) == s3_components(url)


def test_combine_csv_files(tmp_path):
    first = tmp_path / 'first.csv'
    first.write_text('a,b\n1,2\n3,4\n')
    second = tmp_path / 'second.csv'
    second.write_text('a,c\n5,6\n')
    output = tmp_path / 'combined.csv'

    combine_csv_files([str(first), str(second)], str(output))

    assert output.read_text().splitlines() == ['a,b,c', '1,2,', '3,4,', '5,,6']


def test_combine_csv_files_keeps_quoted_values(tmp_path):
    first = tmp_path / 'first.csv'
    first.write_text('name,note\nx,"has, comma"\n')
    output = tmp_path / 'combined.csv'

    combine_csv_files([str(first)], str(output))

    assert output.read_text().splitlines() == ['name,note', 'x,"has, comma"']


def test_combine_csv_files_with_no_inputs(tmp_path):
    output = tmp_path / 'combined.csv'

    combine_csv_files([], str(output))

    assert output.read_text() == ''
