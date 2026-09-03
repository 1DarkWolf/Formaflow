"""Settings used only to collect static assets while building the container image."""

from .base import *  # noqa: F403

DEBUG = False
ALLOWED_HOSTS = ["build.invalid"]
DATABASES = {  # noqa: F405
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405
STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
}
