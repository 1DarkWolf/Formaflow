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
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
DATABASES["default"]["OPTIONS"] = {
    "sslmode": os.getenv("POSTGRES_SSLMODE", "require"),
}

SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", default=True)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", default=True)
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", default=True)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"

if env_bool("DJANGO_TRUST_PROXY_HEADERS", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "25"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", default=False)
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "10"))

MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405
STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
}
