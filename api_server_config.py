from os.path import abspath, dirname

from api_server.default_config import config

here = dirname(abspath(__file__))

config.update(
    {
        "db_url": f"sqlite:///{here}/api-server.db",
    }
)
