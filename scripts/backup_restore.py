"""Encrypted PostgreSQL and private-upload backup for Forma Flow."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

DATABASE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class BackupError(RuntimeError):
    pass


def _required_env(name):
    value = os.getenv(name, "")
    if not value:
        raise BackupError(f"A variável {name} é obrigatória.")
    return value


def _fernet():
    try:
        return Fernet(_required_env("BACKUP_ENCRYPTION_KEY").encode())
    except (TypeError, ValueError) as error:
        raise BackupError("BACKUP_ENCRYPTION_KEY não é uma chave Fernet válida.") from error


def _database_environment():
    return {
        "name": _required_env("POSTGRES_DB"),
        "user": _required_env("POSTGRES_USER"),
        "password": _required_env("POSTGRES_PASSWORD"),
        "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "port": os.getenv("POSTGRES_PORT", "5432"),
    }


def _run(command, *, password):
    environment = os.environ.copy()
    environment["PGPASSWORD"] = password
    try:
        subprocess.run(command, check=True, env=environment)
    except FileNotFoundError as error:
        raise BackupError(f"O executável {command[0]} não está instalado.") from error
    except subprocess.CalledProcessError as error:
        raise BackupError(f"O comando {command[0]} terminou com erro.") from error


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _files(root):
    return sorted(path for path in root.rglob("*") if path.is_file())


def _write_manifest(payload):
    manifest = {
        "format": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "files": {path.relative_to(payload).as_posix(): _sha256(path) for path in _files(payload)},
    }
    (payload / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _verify_manifest(payload):
    manifest_path = payload / "manifest.json"
    if not manifest_path.is_file():
        raise BackupError("O manifesto do backup não existe.")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected = manifest["files"]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise BackupError("O manifesto do backup é inválido.") from error
    actual_paths = {
        path.relative_to(payload).as_posix() for path in _files(payload) if path != manifest_path
    }
    if actual_paths != set(expected):
        raise BackupError("O conteúdo do backup não corresponde ao manifesto.")
    for relative, expected_hash in expected.items():
        if _sha256(payload / relative) != expected_hash:
            raise BackupError("A integridade do backup não pôde ser confirmada.")


def _archive(payload, destination):
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in _files(payload):
            archive.write(path, path.relative_to(payload).as_posix())


def _safe_extract(archive_path, destination):
    root = destination.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            target = (root / member.filename).resolve()
            if target != root and root not in target.parents:
                raise BackupError("O backup contém um caminho inseguro.")
        archive.extractall(root)


def create_backup(*, output, uploads):
    database = _database_environment()
    output = Path(output).expanduser().resolve()
    uploads = Path(uploads).expanduser().resolve()
    if output.exists():
        raise BackupError("O ficheiro de destino já existe.")
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="formaflow-backup-") as temporary:
        root = Path(temporary)
        payload = root / "payload"
        payload.mkdir()
        database_dump = payload / "database.dump"
        _run(
            [
                "pg_dump",
                "--format=custom",
                "--no-owner",
                "--no-privileges",
                f"--host={database['host']}",
                f"--port={database['port']}",
                f"--username={database['user']}",
                f"--file={database_dump}",
                database["name"],
            ],
            password=database["password"],
        )
        upload_copy = payload / "private_uploads"
        if uploads.is_dir():
            shutil.copytree(uploads, upload_copy)
        else:
            upload_copy.mkdir()
        _write_manifest(payload)
        archive_path = root / "backup.zip"
        _archive(payload, archive_path)
        with tempfile.NamedTemporaryFile(
            prefix=f".{output.name}.", suffix=".tmp", dir=output.parent, delete=False
        ) as temporary_output_file:
            temporary_output = Path(temporary_output_file.name)
        try:
            temporary_output.write_bytes(_fernet().encrypt(archive_path.read_bytes()))
            temporary_output.replace(output)
        finally:
            temporary_output.unlink(missing_ok=True)
    return output


def restore_backup(*, source, target_database, uploads_target, allow_source_database=False):
    database = _database_environment()
    source = Path(source).expanduser().resolve()
    uploads_target = Path(uploads_target).expanduser().resolve()
    if not source.is_file():
        raise BackupError("O ficheiro de backup não existe.")
    if not DATABASE_NAME_PATTERN.fullmatch(target_database):
        raise BackupError("O nome da base de destino contém caracteres inválidos.")
    if target_database == database["name"] and not allow_source_database:
        raise BackupError("Restaure primeiro para uma base separada e vazia.")
    if uploads_target.exists() and (not uploads_target.is_dir() or any(uploads_target.iterdir())):
        raise BackupError("A pasta de ficheiros de destino tem de estar vazia.")

    with tempfile.TemporaryDirectory(prefix="formaflow-restore-") as temporary:
        root = Path(temporary)
        archive_path = root / "backup.zip"
        try:
            archive_path.write_bytes(_fernet().decrypt(source.read_bytes()))
        except InvalidToken as error:
            raise BackupError("A chave ou o ficheiro de backup não são válidos.") from error
        payload = root / "payload"
        payload.mkdir()
        _safe_extract(archive_path, payload)
        _verify_manifest(payload)
        _run(
            [
                "pg_restore",
                "--exit-on-error",
                "--no-owner",
                "--no-privileges",
                f"--host={database['host']}",
                f"--port={database['port']}",
                f"--username={database['user']}",
                f"--dbname={target_database}",
                str(payload / "database.dump"),
            ],
            password=database["password"],
        )
        uploads_target.mkdir(parents=True, exist_ok=True)
        for item in (payload / "private_uploads").iterdir():
            destination = uploads_target / item.name
            if item.is_dir():
                shutil.copytree(item, destination)
            else:
                shutil.copy2(item, destination)
    return uploads_target


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="operation", required=True)
    backup = subparsers.add_parser("backup", help="Criar um backup cifrado.")
    backup.add_argument("--output", required=True)
    backup.add_argument("--uploads", default=os.getenv("PRIVATE_UPLOAD_ROOT", "private_uploads"))
    restore = subparsers.add_parser("restore", help="Restaurar para uma base separada e vazia.")
    restore.add_argument("--input", required=True)
    restore.add_argument("--target-database", required=True)
    restore.add_argument("--uploads-target", required=True)
    restore.add_argument("--allow-source-database", action="store_true")
    return parser


def main():
    arguments = _parser().parse_args()
    try:
        if arguments.operation == "backup":
            path = create_backup(output=arguments.output, uploads=arguments.uploads)
            print(f"Backup cifrado criado em {path}")
        else:
            restore_backup(
                source=arguments.input,
                target_database=arguments.target_database,
                uploads_target=arguments.uploads_target,
                allow_source_database=arguments.allow_source_database,
            )
            print("Restauro concluído; valide a aplicação antes de promover esta base.")
    except BackupError as error:
        raise SystemExit(f"Erro: {error}") from error


if __name__ == "__main__":
    main()
