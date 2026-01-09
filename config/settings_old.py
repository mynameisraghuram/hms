import os

env = os.getenv("DJANGO_ENV", "local").lower()

if env == "prod":
    from .settings.prod import *  # noqa
else:
    from .settings.local import *  # noqa
