from enum import Enum
import os

from dotenv import load_dotenv
from typing import cast


Environment = Enum('Environment', ['SBX', 'SIT', 'UAT', 'PROD'])

HOSTNAMES = {
    Environment.SBX: 'harmony.sbx.earthdata.nasa.gov',
    Environment.SIT: 'harmony.sit.earthdata.nasa.gov',
    Environment.UAT: 'harmony.uat.earthdata.nasa.gov',
    Environment.PROD: 'harmony.earthdata.nasa.gov',
}


class Config:
    """Runtime configuation variables including defaults and environment vars.

    Example:
    >>> cfg = Config()
    >>> cfg.foo
    'bar'

    Parameters:
        None
    """

    config = {
        'NUM_REQUESTS_WORKERS': '3',  # increase for servers
        'DOWNLOAD_CHUNK_SIZE': str(4 * 1024 * 1024)  # recommend 16MB for servers
    }

    def __init__(self, environment: Environment = Environment.PROD) -> None:
        load_dotenv()
        for k, v in Config.config.items():
            setattr(self, k, v)
        self.environment = environment

    @property
    def harmony_hostname(self):
        return HOSTNAMES[self.environment]

    @property
    def edl_validation_url(self):
        return f'https://{self.harmony_hostname}/jobs'

    def __getattribute__(self, name: str) -> str:
        """Overrides attribute retrieval for instances of this class. Attribute lookup follow this
            order:
            - .env file variables
            - OS environment variables
            - object attributes that match ``name``
        This dunder method is not called directly.

        Parameters:
            name (str): An EDL username.

        Returns:
            (str): The value of the reference attribute
        """
        var = os.getenv(name.upper())
        if var is None:
            try:
                var = object.__getattribute__(self, name)
            except AttributeError:
                var = None
        return cast(str, var)
