"""Local development settings."""

import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import BASE_DIR, env_bool, env_list, postgres_database

DEBUG = env_bool("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")
CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "http://127.0.0.1:8000,http://localhost:8000",
)

database_engine = os.getenv("DJANGO_DATABASE_ENGINE", "postgresql").lower()

if database_engine == "sqlite":
    DATABASES = {  # noqa: F405
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
elif database_engine == "postgresql":
    DATABASES = {"default": postgres_database()}  # noqa: F405
else:
    raise ImproperlyConfigured("DJANGO_DATABASE_ENGINE deve ser 'postgresql' ou 'sqlite'.")

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
