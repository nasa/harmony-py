import os
from dotenv import load_dotenv


load_dotenv()


class Config():
    """Runtime configuation variables including defaults and environment vars.

    Example:
    >>> cfg = Config()
    >>> cfg.auth_server
    uat.urs.earthdata.nasa.gov
    """

    config = {
        'AUTH_HOST': 'uat.urs.earthdata.nasa.gov'
    }

    def __init__(self):
        for k, v in Config.config.items():
            setattr(self, k, v)

    def __getattribute__(self, name):
        """
        Overrides attribute retrieval for instances of this class. Attribute lookup follow this
        order:
        - .env file variables
        - OS environment variables
        - object attributes that match ``name``

        Parameters
        ----------
        name : string
            The name of the object attribute to look up.

        Returns
        -------
        string | None
            The value of the referenced attribute.
        """
        var = os.getenv(name.upper())
        if var is None:
            try:
                var = object.__getattribute__(self, name)
            except AttributeError:
                var = None
        return var
