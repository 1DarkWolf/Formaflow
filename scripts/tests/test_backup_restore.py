import io
import json
import os
import tempfile
import zipfile
from pathlib import Path
from unittest import TestCase, mock

from cryptography.fernet import Fernet

from scripts.backup_restore import (
    BackupError,
    _safe_extract,
    _verify_manifest,
    _write_manifest,
    create_backup,
    restore_backup,
)


class BackupIntegrityTests(TestCase):
    def test_created_backup_is_encrypted_and_contains_database_and_uploads(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            uploads = root / "uploads"
            uploads.mkdir()
            (uploads / "evidencia.pdf").write_bytes(b"%PDF-ficticio")
            output = root / "backup.ffbackup"
            encryption_key = Fernet.generate_key()

            def create_fake_dump(command, *, password):
                self.assertEqual(password, "test-only")
                dump_argument = next(item for item in command if item.startswith("--file="))
                Path(dump_argument.removeprefix("--file=")).write_bytes(b"postgres-dump")

            environment = {
                "POSTGRES_DB": "formaflow",
                "POSTGRES_USER": "formaflow",
                "POSTGRES_PASSWORD": "test-only",
                "BACKUP_ENCRYPTION_KEY": encryption_key.decode(),
            }
            with (
                mock.patch.dict(os.environ, environment),
                mock.patch("scripts.backup_restore._run", side_effect=create_fake_dump),
            ):
                create_backup(output=output, uploads=uploads)

            decrypted = Fernet(encryption_key).decrypt(output.read_bytes())
            with zipfile.ZipFile(io.BytesIO(decrypted)) as archive:
                self.assertEqual(
                    set(archive.namelist()),
                    {"database.dump", "private_uploads/evidencia.pdf", "manifest.json"},
                )

    def test_manifest_detects_a_changed_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            payload = Path(temporary)
            database = payload / "database.dump"
            database.write_bytes(b"backup-original")
            _write_manifest(payload)
            _verify_manifest(payload)

            database.write_bytes(b"backup-alterado")

            with self.assertRaises(BackupError):
                _verify_manifest(payload)

    def test_safe_extract_rejects_parent_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "inseguro.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("../fora.txt", "conteúdo")

            with self.assertRaises(BackupError):
                _safe_extract(archive_path, root / "destino")

    def test_manifest_contains_only_relative_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            payload = Path(temporary)
            (payload / "private_uploads").mkdir()
            (payload / "private_uploads" / "ficheiro.pdf").write_bytes(b"%PDF-demo")

            _write_manifest(payload)
            manifest = json.loads((payload / "manifest.json").read_text(encoding="utf-8"))

            self.assertEqual(list(manifest["files"]), ["private_uploads/ficheiro.pdf"])

    @mock.patch.dict(
        "os.environ",
        {
            "POSTGRES_DB": "formaflow",
            "POSTGRES_USER": "formaflow",
            "POSTGRES_PASSWORD": "test-only",
        },
    )
    def test_restore_rejects_a_file_as_upload_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "backup.ffbackup"
            source.write_bytes(b"encrypted-placeholder")
            destination = root / "not-a-directory"
            destination.write_text("occupied", encoding="utf-8")

            with self.assertRaises(BackupError):
                restore_backup(
                    source=source,
                    target_database="formaflow_restore",
                    uploads_target=destination,
                )
