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


def test_combine_csv_files_writes_lf_line_endings(tmp_path):
    first = tmp_path / 'first.csv'
    first.write_bytes(b'a,b\n1,2\n')
    second = tmp_path / 'second.csv'
    second.write_bytes(b'a,b\r\n3,4\r\n')
    output = tmp_path / 'combined.csv'

    combine_csv_files([str(first), str(second)], str(output), id_column='id', ids=['x', 'y'])

    assert output.read_bytes() == b'id,a,b\nx,1,2\ny,3,4\n'


def test_combine_csv_files_with_no_inputs(tmp_path):
    output = tmp_path / 'combined.csv'

    combine_csv_files([], str(output))

    assert output.read_text() == ''


def test_combine_csv_files_with_id_column(tmp_path):
    first = tmp_path / 'first.csv'
    first.write_text('a,b\n1,2\n3,4\n')
    second = tmp_path / 'second.csv'
    second.write_text('a\n5\n')
    output = tmp_path / 'combined.csv'

    combine_csv_files(
        [str(first), str(second)], str(output), id_column='job_id', ids=['job-1', 'job-2']
    )

    assert output.read_text().splitlines() == ['job_id,a,b', 'job-1,1,2', 'job-1,3,4', 'job-2,5,']


def test_combine_csv_files_rejects_existing_id_column(tmp_path):
    first = tmp_path / 'first.csv'
    first.write_text('job_id,a\nx,1\n')

    with pytest.raises(ValueError, match='already has a column named job_id'):
        combine_csv_files([str(first)], str(tmp_path / 'combined.csv'), 'job_id', ['job-1'])


@pytest.mark.parametrize(
    'id_column, ids',
    [('job_id', None), (None, ['job-1']), ('job_id', ['job-1', 'job-2'])],
)
def test_combine_csv_files_rejects_mismatched_ids(tmp_path, id_column, ids):
    first = tmp_path / 'first.csv'
    first.write_text('a\n1\n')

    with pytest.raises(ValueError):
        combine_csv_files([str(first)], str(tmp_path / 'combined.csv'), id_column, ids)
