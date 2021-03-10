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
    (Environment.SBX, 'https://harmony.sbx.earthdata.nasa.gov/jobs'),
    (Environment.SIT, 'https://harmony.sit.earthdata.nasa.gov/jobs'),
    (Environment.UAT, 'https://harmony.uat.earthdata.nasa.gov/jobs'),
    (Environment.PROD, 'https://harmony.earthdata.nasa.gov/jobs')
])
def test_validation_url_matches_environment(env, url):
    config = Config(env)

    assert config.edl_validation_url == url
