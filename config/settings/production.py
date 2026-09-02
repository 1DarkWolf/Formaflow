"""Production settings with fail-fast validation."""

import os

from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import env_bool, env_list, postgres_database

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

if not SECRET_KEY or SECRET_KEY == "change-this-value-in-your-local-env-file":
    raise ImproperlyConfigured("DJANGO_SECRET_KEY é obrigatória em produção.")
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS é obrigatória em produção.")
if not POSTGRES_PASSWORD or POSTGRES_PASSWORD == "change-this-password":
    raise ImproperlyConfigured("POSTGRES_PASSWORD é obrigatória em produção.")
if not os.getenv("DATA_ENCRYPTION_KEY"):
    raise ImproperlyConfigured("DATA_ENCRYPTION_KEY é obrigatória em produção.")
if not os.getenv("DATA_HASH_KEY"):
    raise ImproperlyConfigured("DATA_HASH_KEY é obrigatória em produção.")

try:
    Fernet(DATA_ENCRYPTION_KEY.encode())  # noqa: F405
except (TypeError, ValueError) as error:
    raise ImproperlyConfigured("DATA_ENCRYPTION_KEY não é uma chave Fernet válida.") from error

DEBUG = False
DATABASES = {"default": postgres_database()}  # noqa: F405

SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "25"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", default=False)

STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
}
