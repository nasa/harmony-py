import os

from dotenv import load_dotenv
from typing import cast


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
        'NUM_REQUESTS_WORKERS': '8',
        'EDL_VALIDATION_URL': 'https://harmony.earthdata.nasa.gov/jobs',
    }

    def __init__(self) -> None:
        load_dotenv()
        for k, v in Config.config.items():
            setattr(self, k, v)

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
