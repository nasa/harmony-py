import pytest

from harmony.config import Config, Environment


def test_config_from_env(mocker):
    expected_value = 'bar'
    mocker.patch('harmony.config.os.getenv', return_value=expected_value)
    config = Config()
    assert config.FOO == expected_value


def test_config_not_there():
    config = Config()
    assert config.ASDF is None


def test_config_built_in():
    config = Config()
    assert config.NUM_REQUESTS_WORKERS is not None


@pytest.mark.parametrize('env,url', [
    (Environment.LOCAL, 'localhost:3000'),
    (Environment.SBX, 'harmony.sbx.earthdata.nasa.gov'),
    (Environment.SIT, 'harmony.sit.earthdata.nasa.gov'),
    (Environment.UAT, 'harmony.uat.earthdata.nasa.gov'),
    (Environment.PROD, 'harmony.earthdata.nasa.gov')
])
def test_harmony_hostname_matches_environment(env, url):
    config = Config(env)

    assert config.harmony_hostname == url


@pytest.mark.parametrize('env,url', [
    (Environment.LOCAL, 'http'),
    (Environment.SBX, 'https'),
    (Environment.SIT, 'https'),
    (Environment.UAT, 'https'),
    (Environment.PROD, 'https')
])
def test_url_scheme_matches_environment(env, url):
    config = Config(env)

    assert config.url_scheme == url


@pytest.mark.parametrize('env,url', [
    (Environment.LOCAL, 'http://localhost:3000'),
    (Environment.SBX, 'https://harmony.sbx.earthdata.nasa.gov'),
    (Environment.SIT, 'https://harmony.sit.earthdata.nasa.gov'),
    (Environment.UAT, 'https://harmony.uat.earthdata.nasa.gov'),
    (Environment.PROD, 'https://harmony.earthdata.nasa.gov')
])
def test_root_url_matches_environment(env, url):
    config = Config(env)

    assert config.root_url == url


@pytest.mark.parametrize('env,url', [
    (Environment.LOCAL, 'http://localhost:3000/jobs'),
    (Environment.SBX, 'https://harmony.sbx.earthdata.nasa.gov/jobs'),
    (Environment.SIT, 'https://harmony.sit.earthdata.nasa.gov/jobs'),
    (Environment.UAT, 'https://harmony.uat.earthdata.nasa.gov/jobs'),
    (Environment.PROD, 'https://harmony.earthdata.nasa.gov/jobs')
])
def test_edl_validation_url_matches_environment(env, url):
    config = Config(env)

    assert config.edl_validation_url == url
