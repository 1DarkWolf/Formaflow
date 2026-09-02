"""Automated test settings."""

import os

from .base import *  # noqa: F403
from .base import BASE_DIR, postgres_database

SECRET_KEY = "test-only-secret-key-never-used-outside-tests"
DEBUG = False

test_database_engine = os.getenv("DJANGO_TEST_DATABASE_ENGINE", "sqlite").lower()

if test_database_engine == "postgresql":
    DATABASES = {"default": postgres_database()}  # noqa: F405
else:
    DATABASES = {  # noqa: F405
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
MEDIA_ROOT = BASE_DIR / "tmp" / "test_uploads"

STORAGES = {  # noqa: F405
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": MEDIA_ROOT},
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
