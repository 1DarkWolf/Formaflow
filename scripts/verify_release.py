"""Exercise a clean, offline Forma Flow installation before a release."""

import os
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run(*arguments, environment):
    subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "manage.py"), *arguments],
        check=True,
        cwd=PROJECT_ROOT,
        env=environment,
    )


def main():
    with tempfile.TemporaryDirectory(prefix="formaflow-release-") as temporary:
        temporary_root = Path(temporary)
        demonstration_password = f"Demo-{secrets.token_urlsafe(24)}-A1!"
        test_environment = os.environ.copy()
        test_environment.update(
            {
                "DJANGO_SETTINGS_MODULE": "config.settings.test",
                "DJANGO_TEST_DATABASE_ENGINE": "sqlite",
                "DJANGO_TEST_SQLITE_PATH": str(temporary_root / "clean.sqlite3"),
                "DJANGO_TEST_UPLOAD_ROOT": str(temporary_root / "private_uploads"),
                "FORMAFLOW_DEMO_PASSWORD": demonstration_password,
            }
        )
        _run("migrate", "--noinput", environment=test_environment)
        _run("carregar_cenario_demonstracao", environment=test_environment)
        _run("carregar_cenario_demonstracao", environment=test_environment)
        _run("processar_alertas", environment=test_environment)
        _run("check", environment=test_environment)
        _run("makemigrations", "--check", "--dry-run", environment=test_environment)

        production_environment = os.environ.copy()
        production_environment.update(
            {
                "DJANGO_SECRET_KEY": secrets.token_urlsafe(64),
                "DJANGO_ALLOWED_HOSTS": "example.test",
                "DJANGO_CSRF_TRUSTED_ORIGINS": "https://example.test",
                "POSTGRES_DB": "formaflow",
                "POSTGRES_USER": "formaflow",
                "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
                "POSTGRES_HOST": "127.0.0.1",
                "POSTGRES_SSLMODE": "require",
                "DATA_ENCRYPTION_KEY": Fernet.generate_key().decode(),
                "DATA_HASH_KEY": secrets.token_urlsafe(48),
                "DJANGO_STATIC_ROOT": str(temporary_root / "staticfiles"),
            }
        )
        _run(
            "check",
            "--deploy",
            "--fail-level",
            "WARNING",
            "--settings=config.settings.production",
            environment=production_environment,
        )

    print("Verificação de entrega concluída numa instalação temporária limpa.")


if __name__ == "__main__":
    main()
